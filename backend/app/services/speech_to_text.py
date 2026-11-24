"""Speech-to-text service with provider adapters and ffmpeg audio preprocessing.

Enforces zero-storage guarantees: all audio transcoding happens in ephemeral temp files
that are strictly cleaned up inside `finally` blocks.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
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


def validate_bangla_script(text: str, min_bangla_ratio: float = 0.5) -> None:
    """Validate that transcribed text contains predominantly Bengali script.

    If fewer than ~50% of the alphabetic characters belong to the Bengali Unicode block (\u0980-\u09FF),
    raise KothaError(422, 'ASR_NON_BANGLA', 'কথা বোঝা যায়নি, আবার বলুন বা লিখে দিন').
    Strictly avoids logging or leaking the transcript text.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        raise KothaError(
            422,
            "NO_SPEECH_DETECTED",
            "No speech was detected. Please record again, closer to the microphone.",
        )
    letters = [ch for ch in cleaned if ch.isalpha()]
    if letters:
        bangla_chars = sum(1 for ch in letters if "\u0980" <= ch <= "\u09ff")
        ratio = bangla_chars / len(letters)
        if ratio < min_bangla_ratio:
            raise KothaError(
                422,
                "ASR_NON_BANGLA",
                "কথা বোঝা যায়নি, আবার বলুন বা লিখে দিন (Speech could not be recognized as Bangla. Please record again or type your note).",
            )
    else:
        has_bangla = any("\u0980" <= ch <= "\u09ff" for ch in cleaned)
        if not has_bangla:
            raise KothaError(
                422,
                "ASR_NON_BANGLA",
                "কথা বোঝা যায়নি, আবার বলুন বা লিখে দিন (Speech could not be recognized as Bangla. Please record again or type your note).",
            )


def process_audio(raw_bytes: bytes, max_bytes: int) -> tuple[bytes, float]:
    """Validate raw audio container, transcode to 16kHz mono PCM 16-bit WAV with ffmpeg,
    and verify duration <= 90s.
    Always deletes temporary files in a finally block. Returns (wav_bytes, duration_seconds).
    """
    validate_audio(raw_bytes, max_bytes)
    if not shutil.which("ffmpeg"):
        raise KothaError(503, "FFMPEG_NOT_INSTALLED", "Audio processing requires ffmpeg on the server.")

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
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except FileNotFoundError:
            raise KothaError(503, "FFMPEG_NOT_INSTALLED", "Audio processing requires ffmpeg on the server.")
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
    """Translate transport and provider errors into clean KothaError without leaking credentials or transcripts."""
    if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
        raise KothaError(
            504,
            "ASR_TIMEOUT",
            "স্পিচ রিকগনিশন সার্ভার সময়মতো সাড়া দেয়নি (ASR provider timed out). অনুগ্রহ করে আবার চেষ্টা করুন বা টাইপ করুন।",
        ) from exc
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        error_type = "unknown_error"
        safe_reason = f"HTTP {status}"
        try:
            body = exc.response.json()
            if isinstance(body, dict):
                err = body.get("error")
                if isinstance(err, dict):
                    error_type = str(err.get("type") or err.get("code") or "error")
                    raw_msg = str(err.get("message") or "")
                    # Sanitize: strip any potential user text / transcripts, keep short parameter/type description
                    safe_msg = re.sub(r"[^a-zA-Z0-9_\-\.\:\s`]", "", raw_msg)[:100].strip()
                    safe_reason = f"{error_type}: {safe_msg}" if safe_msg else error_type
                elif isinstance(err, str):
                    error_type = "error"
                    safe_reason = re.sub(r"[^a-zA-Z0-9_\-\.\:\s`]", "", err)[:100].strip()
        except Exception:
            pass

        log.warning(
            "stt_upstream_error provider=%s status=%s error_type=%s reason=%s",
            provider,
            status,
            error_type,
            safe_reason,
        )

        if 400 <= status < 500:
            raise KothaError(
                502,
                "ASR_PROVIDER_REJECTED",
                f"স্পিচ রিকগনিশন সেবা অনুরোধটি প্রত্যাখ্যান করেছে ({safe_reason}). অনুগ্রহ করে আবার চেষ্টা করুন বা টাইপ করে লিখুন।",
            ) from exc
        raise KothaError(
            502,
            "ASR_PROVIDER_UNAVAILABLE",
            f"স্পিচ রিকগনিশন সেবা সাময়িকভাবে অনুপলব্ধ ({safe_reason}). অনুগ্রহ করে কিছুক্ষণ পর চেষ্টা করুন বা টাইপ করে লিখুন।",
        ) from exc

    raise KothaError(
        502,
        "ASR_PROVIDER_UNAVAILABLE",
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
            validate_bangla_script(text)
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
                    headers={
                        "Authorization": f"Bearer {self._key}",
                        "Content-Type": content_type or "audio/wav",
                        "x-wait-for-model": "true",
                    },
                    params={"language": "bn", "task": "transcribe"},
                    content=audio_bytes,
                )
                r.raise_for_status()
                text = (r.json().get("text") or "").strip()
                validate_bangla_script(text)
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
                    data={
                        "model": self._model,
                        "language": "bn",
                        "response_format": "json",
                        "prompt": "বাংলায় বলুন।",
                    },
                    files={"file": ("recording.wav", audio_bytes, content_type or "audio/wav")},
                )
                r.raise_for_status()
                text = (r.json().get("text") or "").strip()
                validate_bangla_script(text)
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
