"""Speech-to-text adapters. Confidence is returned only if the provider supplies it."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import Settings
from app.core.exceptions import KothaError
from app.services.providers.llm import raise_for_provider


@dataclass
class STTResult:
    text: str
    confidence: float | None
    provider: str
    model: str


class STTProvider(Protocol):
    name: str

    async def transcribe(self, audio: bytes, content_type: str) -> STTResult: ...


class HFInferenceSTT:
    """Hugging Face Inference (hf-inference) automatic-speech-recognition endpoint."""

    name = "hf_inference"

    def __init__(self, s: Settings):
        self._model, self._key, self._timeout = s.speech_model, s.speech_api_key, s.provider_timeout_seconds
        self._base = (s.speech_base_url or "https://router.huggingface.co/hf-inference/models").rstrip("/")

    async def transcribe(self, audio: bytes, content_type: str) -> STTResult:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(
                    f"{self._base}/{self._model}",
                    headers={"Authorization": f"Bearer {self._key}", "Content-Type": content_type or "audio/webm"},
                    content=audio,
                )
                r.raise_for_status()
                text = (r.json().get("text") or "").strip()
        except (httpx.HTTPError, ValueError, AttributeError) as exc:
            raise_for_provider(exc, "hf_inference")
            raise
        return STTResult(text, None, self.name, self._model)


class OpenAICompatSTT:
    """OpenAI-compatible /audio/transcriptions (OpenAI, Groq, etc.)."""

    name = "openai_compatible"

    def __init__(self, s: Settings):
        self._model, self._key, self._timeout = s.speech_model, s.speech_api_key, s.provider_timeout_seconds
        self._base = (s.speech_base_url or "https://api.openai.com/v1").rstrip("/")

    async def transcribe(self, audio: bytes, content_type: str) -> STTResult:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(
                    f"{self._base}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self._key}"},
                    data={"model": self._model, "language": "bn", "response_format": "json"},
                    files={"file": ("audio.webm", audio, content_type or "audio/webm")},
                )
                r.raise_for_status()
                text = (r.json().get("text") or "").strip()
        except (httpx.HTTPError, ValueError, AttributeError) as exc:
            raise_for_provider(exc, "openai_compatible")
            raise
        return STTResult(text, None, self.name, self._model)


def stt_configured(s: Settings) -> bool:
    return s.speech_provider in ("hf_inference", "openai_compatible") and bool(s.speech_api_key and s.speech_model)


def get_stt(s: Settings) -> STTProvider:
    if not stt_configured(s):
        raise KothaError(503, "PROVIDER_NOT_CONFIGURED",
                         "No speech provider is configured (set SPEECH_PROVIDER, SPEECH_MODEL, SPEECH_API_KEY), or use demo mode.")
    return HFInferenceSTT(s) if s.speech_provider == "hf_inference" else OpenAICompatSTT(s)
