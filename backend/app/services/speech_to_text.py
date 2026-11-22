"""Speech-to-text service with provider adapters and ffmpeg audio preprocessing.

Enforces zero-storage guarantees: all audio transcoding happens in ephemeral temp files
that are strictly cleaned up inside `finally` blocks.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from app.config import Settings
from app.core.exceptions import KothaError
from app.core.logging import get_logger
from app.core.security import validate_audio

log = get_logger("stt")


@dataclass
class STTResult:
    text: str
    confidence: float | None
    provider: str
    model: str


class SpeechToTextProvider(Protocol):
    name: str

    async def transcribe(self, audio_bytes: bytes, content_type: str = "audio/wav") -> STTResult:
        ...


def process_audio(raw_bytes: bytes, max_bytes: int) -> tuple[bytes, float]:
    """Validate raw audio container, transcode to 16kHz mono PCM 16-bit WAV with ffmpeg,
    and verify duration <= 90s.
    Always deletes temporary files in a finally block. Returns (wav_bytes, duration_seconds).
    """
    validate_audio(raw_bytes, max_bytes)

    in_fd, in_path = tempfile.mkstemp(suffix=".raw")
    out_path = in_path + "_converted.wav"
    try:
        with os.fdopen(in_fd, "wb") as f:
            f.write(raw_bytes)

        # Transcode to 16kHz mono 16-bit PCM WAV using ffmpeg
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            in_path,
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            out_path,
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0 or not os.path.exists(out_path):
            log.warning("ffmpeg failed: %s", res.stderr.decode("utf-8", errors="ignore")[:300])
            raise KothaError(415, "AUDIO_CONVERSION_FAILED", "Could not process audio format. Please record again.")

        # Inspect duration via wave
        with wave.open(out_path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            duration = frames / float(rate) if rate > 0 else 0.0

        if duration < 0.1 or frames == 0:
            raise KothaError(422, "NO_SPEECH_DETECTED", "The recording is empty or silent. Please record again.")
        if duration > 90.5:
            raise KothaError(413, "AUDIO_TOO_LONG", "The recording exceeds the maximum limit of 90 seconds.")

        wav_bytes = Path(out_path).read_bytes()
        return wav_bytes, duration
    finally:
        for p in (in_path, out_path):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


def raise_for_stt(exc: Exception, provider: str) -> None:
    """Translate transport and provider errors into clean KothaError without leaking credentials."""
    if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
        raise KothaError(
            504,
            "PROVIDER_TIMEOUT",
            "স্পিচ রিকগনিশন সার্ভার সময়মতো সাড়া দেয়নি (ASR provider timed out). অনুগ্রহ করে আবার চেষ্টা করুন বা টাইপ করুন।",
        ) from exc
    if isinstance(exc, httpx.HTTPStatusError):
        log.warning("provider=%s status=%s", provider, exc.response.status_code)
        raise KothaError(
            502,
            "PROVIDER_ERROR",
            f"স্পিচ রিকগনিশন সেবা ত্রুটি দিয়েছে (HTTP {exc.response.status_code}). অনুগ্রহ করে টাইপ করুন বা ডেমো মোড ব্যবহার করুন।",
        ) from exc
    raise KothaError(
        502,
        "PROVIDER_UNREACHABLE",
        f"স্পিচ রিকগনিশন সেবা এই মুহূর্তে অনুপলব্ধ ({provider} unreachable). অনুগ্রহ করে টাইপ করে লিখুন বা ডেমো মোড ব্যবহার করুন।",
    ) from exc


class LocalTransformersSTT:
    """Local Hugging Face Transformers pipeline adapter (lazy-loaded on first use)."""

    name = "local_transformers"

    def __init__(self, s: Settings):
        self._model = s.speech_model or "openai/whisper-tiny"
        self._pipeline = None

    def _get_pipeline(self):
        if self._pipeline is None:
            try:
                from transformers import pipeline  # lazy import
                self._pipeline = pipeline("automatic-speech-recognition", model=self._model)
            except Exception as exc:
                raise KothaError(
                    502,
                    "LOCAL_ASR_UNAVAILABLE",
                    f"Local Hugging Face transformers pipeline could not be loaded for {self._model}: {exc}",
                ) from exc
        return self._pipeline

    async def transcribe(self, audio_bytes: bytes, content_type: str = "audio/wav") -> STTResult:
        pipe = self._get_pipeline()
        loop = asyncio.get_running_loop()
        try:
            res = await loop.run_in_executor(
                None,
                lambda: pipe(audio_bytes, generate_kwargs={"language": "bn", "task": "transcribe"}),
            )
            text = (res.get("text") or "").strip()
            return STTResult(text=text, confidence=None, provider=self.name, model=self._model)
        except Exception as exc:
            raise_for_stt(exc, self.name)
            raise


class HFInferenceSTT:
    """Hugging Face Inference API automatic-speech-recognition endpoint."""

    name = "hf_inference"

    def __init__(self, s: Settings):
        self._model = s.speech_model or "bangla-speech-processing/BanglaASR"
        self._key = s.speech_api_key
        self._timeout = s.provider_timeout_seconds
        self._base = (s.speech_base_url or "https://router.huggingface.co/hf-inference/models").rstrip("/")

    async def transcribe(self, audio_bytes: bytes, content_type: str = "audio/wav") -> STTResult:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(
                    f"{self._base}/{self._model}",
                    headers={"Authorization": f"Bearer {self._key}", "Content-Type": content_type or "audio/wav"},
                    content=audio_bytes,
                )
                r.raise_for_status()
                text = (r.json().get("text") or "").strip()
        except Exception as exc:
            raise_for_stt(exc, self.name)
            raise
        return STTResult(text=text, confidence=None, provider=self.name, model=self._model)


class OpenAICompatSTT:
    """OpenAI-compatible /audio/transcriptions endpoint (OpenAI, Groq, etc.)."""

    name = "openai_compatible"

    def __init__(self, s: Settings):
        self._model = s.speech_model or "whisper-1"
        self._key = s.speech_api_key
        self._timeout = s.provider_timeout_seconds
        self._base = (s.speech_base_url or "https://api.openai.com/v1").rstrip("/")

    async def transcribe(self, audio_bytes: bytes, content_type: str = "audio/wav") -> STTResult:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(
                    f"{self._base}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self._key}"},
                    data={"model": self._model, "language": "bn", "response_format": "json"},
                    files={"file": ("recording.wav", audio_bytes, content_type or "audio/wav")},
                )
                r.raise_for_status()
                text = (r.json().get("text") or "").strip()
        except Exception as exc:
            raise_for_stt(exc, self.name)
            raise
        return STTResult(text=text, confidence=None, provider=self.name, model=self._model)


def stt_configured(s: Settings) -> bool:
    if s.speech_provider in ("hf_inference", "openai_compatible"):
        return bool(s.speech_api_key and s.speech_model)
    if s.speech_provider == "local_transformers":
        return bool(s.speech_model)
    return False


def get_stt(s: Settings) -> SpeechToTextProvider:
    if not stt_configured(s):
        raise KothaError(
            503,
            "PROVIDER_NOT_CONFIGURED",
            "No speech provider is configured (set SPEECH_PROVIDER, SPEECH_MODEL, SPEECH_API_KEY in backend/.env), or use demo mode.",
        )
    if s.speech_provider == "local_transformers":
        return LocalTransformersSTT(s)
    if s.speech_provider == "hf_inference":
        return HFInferenceSTT(s)
    return OpenAICompatSTT(s)
