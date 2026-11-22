"""Bangla TTS. The spoken text is built from fixed templates and contains NO patient data,
so nothing sensitive is sent to the TTS provider."""
from __future__ import annotations

import asyncio
import base64
import io

from app.config import Settings
from app.core.exceptions import KothaError
from app.core.logging import get_logger

log = get_logger("tts")

BASE_BN = (
    "আপনার কথা লিখে রাখা হয়েছে। ডাক্তার সেগুলো দেখে আপনাকে আরও কিছু প্রশ্ন করতে পারেন, "
    "যেমন কবে থেকে শুরু হয়েছে, কতটা কষ্ট হচ্ছে, বা কোনো ওষুধ খেয়েছেন কি না। "
    "এটি কোনো রোগ নির্ণয় নয়। সব সিদ্ধান্ত ডাক্তারই নেবেন।"
)
URGENT_BN = (
    "আপনার কথায় এমন লক্ষণ আছে, যার জন্য এখনই জরুরি চিকিৎসা নেওয়া দরকার হতে পারে। "
    "দেরি না করে কাছের স্বাস্থ্যকেন্দ্র বা হাসপাতালে যান, অথবা কাউকে সাহায্যের জন্য ডাকুন। "
)


def build_spoken_text(has_red_flag: bool) -> str:
    return (URGENT_BN + BASE_BN) if has_red_flag else BASE_BN


def _synthesize_gtts(text: str) -> bytes:
    from gtts import gTTS  # imported lazily; optional at import time

    buf = io.BytesIO()
    gTTS(text=text, lang="bn").write_to_fp(buf)
    return buf.getvalue()


async def synthesize(text: str, settings: Settings) -> tuple[str, str, str]:
    """Return (audio_base64, mime_type, provider). Raises KothaError on failure."""
    if settings.tts_provider != "gtts":
        raise KothaError(503, "TTS_NOT_CONFIGURED", "No TTS provider is configured.")
    try:
        audio = await asyncio.wait_for(asyncio.to_thread(_synthesize_gtts, text), timeout=settings.provider_timeout_seconds)
    except Exception as exc:  # network, rate limit, library errors: report honestly
        log.warning("tts_failed error=%s", type(exc).__name__)
        raise KothaError(503, "TTS_FAILED", "Bangla speech could not be generated right now.") from exc
    if not audio:
        raise KothaError(503, "TTS_FAILED", "Bangla speech could not be generated right now.")
    return base64.b64encode(audio).decode("ascii"), "audio/mpeg", "gtts"
