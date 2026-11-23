"""Bangla Text-to-Speech (TTS) service with provider adapter architecture.

The spoken reply is built from a deterministic Bangla TEMPLATE (no LLM, no diagnostic advice).
Audio is synthesized strictly in memory (using BytesIO) and never written to disk.
"""
from __future__ import annotations

import asyncio
import base64
import io
from abc import ABC, abstractmethod
from typing import Any

from app.config import Settings
from app.core.exceptions import KothaError
from app.core.logging import get_logger
from app.schemas.clinical import Item

log = get_logger("tts")

INTRO_BN = "আপনার তথ্য ডাক্তারের কাছে পাঠানোর জন্য লেখা হয়েছে।"
OUTRO_BN = "এটি কোনো রোগ নির্ণয় নয়। ডাক্তারই আপনার চিকিৎসার সিদ্ধান্ত নেবেন।"
URGENT_BN = "আপনার কথায় জরুরি কিছু লক্ষণ দেখা গেছে। শান্ত থাকুন এবং দেরি না করে এখনই নিকটস্থ স্বাস্থ্য কমপ্লেক্স বা হাসপাতালে যোগাযোগ করুন।"


def _synthesize_gtts(text: str) -> bytes:
    from gtts import gTTS
    buf = io.BytesIO()
    tts = gTTS(text=text, lang="bn")
    tts.write_to_fp(buf)
    return buf.getvalue()


def build_spoken_template_text(
    has_urgent_or_emergency: bool,
    uncertain_or_missing: list[Item] | list[dict[str, Any]] | None = None,
) -> str:
    """Build a deterministic, patient-safe spoken Bangla reply from fixed templates.
    
    1. 'আপনার তথ্য ডাক্তারের কাছে পাঠানোর জন্য লেখা হয়েছে।'
    2. 1–3 things the doctor may ask about (from uncertain_or_missing).
    3. Calm urgent care instruction (only if emergency/urgent rule fired).
    4. 'ডাক্তারই আপনার চিকিৎসার সিদ্ধান্ত নেবেন।'
    Never makes a diagnosis.
    """
    parts = [INTRO_BN]

    # 1-3 missing items
    if uncertain_or_missing:
        items = []
        for x in uncertain_or_missing[:3]:
            if isinstance(x, dict):
                items.append(x.get("bn") or x.get("en") or "")
            elif hasattr(x, "bn"):
                items.append(x.bn)
        items = [i.strip() for i in items if i and i.strip()]
        if items:
            parts.append(f"ডাক্তার হয়তো আপনার কাছে জানতে চাইতে পারেন: {', '.join(items)}।")

    # Urgent care instruction if emergency/urgent rule fired
    if has_urgent_or_emergency:
        parts.append(URGENT_BN)

    # Doctor decision reminder
    parts.append(OUTRO_BN)

    return " ".join(parts)


def build_spoken_text(has_red_flag: bool) -> str:
    """Backward compatibility wrapper."""
    return build_spoken_template_text(has_red_flag)


class TextToSpeechProvider(ABC):
    """Abstract interface for Bangla speech synthesis providers."""

    name: str

    @abstractmethod
    async def synthesize(self, text: str) -> tuple[bytes, str]:
        """Synthesize text to audio bytes in memory. Returns (audio_bytes, mime_type)."""
        pass


class GTTSProvider(TextToSpeechProvider):
    """Google Translate TTS adapter (lang='bn'). Zero API keys, outputs standard MP3 in memory."""

    name = "gtts"

    async def synthesize(self, text: str) -> tuple[bytes, str]:
        audio = await asyncio.to_thread(_synthesize_gtts, text)
        if not audio:
            raise KothaError(503, "TTS_FAILED", "gTTS generated empty audio.")
        return audio, "audio/mpeg"


def get_tts_provider(settings: Settings) -> TextToSpeechProvider:
    if settings.tts_provider == "gtts":
        return GTTSProvider()
    raise KothaError(503, "TTS_NOT_CONFIGURED", f"TTS provider '{settings.tts_provider}' is not supported. Supported: 'gtts'.")


async def synthesize(text: str, settings: Settings) -> tuple[str, str, str]:
    """Synthesize Bangla audio in memory. Returns (audio_base64, mime_type, provider_name)."""
    if settings.tts_provider == "none" or not settings.tts_provider:
        raise KothaError(503, "TTS_NOT_CONFIGURED", "No TTS provider is configured.")

    provider = get_tts_provider(settings)
    try:
        audio_bytes, mime = await asyncio.wait_for(
            provider.synthesize(text),
            timeout=settings.provider_timeout_seconds,
        )
    except TimeoutError as exc:
        log.warning("tts_timeout")
        raise KothaError(504, "TTS_TIMEOUT", "TTS generation timed out.") from exc
    except KothaError:
        raise
    except Exception as exc:
        log.warning("tts_failed error=%s", type(exc).__name__)
        raise KothaError(503, "TTS_FAILED", "Bangla speech could not be generated right now.") from exc

    return base64.b64encode(audio_bytes).decode("ascii"), mime, provider.name
