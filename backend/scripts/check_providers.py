#!/usr/bin/env python3
"""Live provider health and capability checker.

Validates end-to-end provider connectivity using the application's own adapters
and configuration settings. Strictly sanitizes output to avoid leaking keys,
tokens, transcript content, or raw model outputs.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import sys
import time
from pathlib import Path

# Set up project root and backend path
backend_dir = Path(__file__).resolve().parent.parent
root_dir = backend_dir.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import Settings, get_settings
from app.core.exceptions import KothaError
from app.services.clinical_extractor import extract
from app.services.dialect_normalizer import normalize
from app.services.speech_to_text import get_stt, process_audio
from app.services.text_to_speech import build_spoken_template_text, get_tts_provider


def _sanitize_error(exc: Exception) -> str:
    """Return a sanitized, credential-free summary of an exception."""
    exc_type = type(exc).__name__
    if isinstance(exc, KothaError):
        return f"{exc_type}: [{exc.code}] (HTTP {exc.status_code})"

    msg = str(exc)
    # Strip potential Bearer tokens or API keys
    msg = re.sub(r"(bearer\s+)[a-zA-Z0-9_\-\.]+", r"\1[REDACTED]", msg, flags=re.I)
    msg = re.sub(r"(key\s*[:=]\s*)[a-zA-Z0-9_\-\.]+", r"\1[REDACTED]", msg, flags=re.I)
    msg = re.sub(r"[a-zA-Z0-9_\-]{24,}", "[REDACTED]", msg)
    # Truncate to avoid leaking payload data
    msg = msg.strip().replace("\n", " ")
    if len(msg) > 100:
        msg = msg[:100] + "..."
    return f"{exc_type}: {msg}" if msg else exc_type


async def check_ffmpeg() -> tuple[bool, str]:
    which_path = shutil.which("ffmpeg")
    if not which_path:
        raise RuntimeError("ffmpeg binary not found in system PATH")
    return True, "ffmpeg found"


async def check_stt(settings: Settings) -> tuple[bool, str]:
    stt = get_stt(settings)
    sample_path = root_dir / "demo_assets" / "audio" / "sample_A.wav"
    if not sample_path.exists():
        raise FileNotFoundError("sample_A.wav missing from demo_assets/audio")

    audio_bytes = sample_path.read_bytes()
    wav_bytes, _ = process_audio(audio_bytes, settings.max_audio_bytes)
    result = await stt.transcribe(wav_bytes, "audio/wav")
    if not result or not result.text or not result.text.strip():
        raise RuntimeError("STT provider returned an empty transcript")
    return True, f"provider={result.provider}, model={result.model or 'default'}"


async def check_normalization(settings: Settings) -> tuple[bool, str]:
    if settings.llm_provider == "none":
        raise KothaError(503, "PROVIDER_NOT_CONFIGURED", "LLM provider is set to none")

    res = await normalize("সকাল থাকি আমার মাথাত বেদনা করের।", settings, use_llm=True)
    if res.source != "llm_with_glossary":
        warnings_str = "; ".join(res.warnings) if res.warnings else "fallback used"
        raise RuntimeError(f"Normalization did not use LLM (source: {res.source}; {warnings_str})")
    return True, f"provider={res.provider}"


async def check_extraction(settings: Settings) -> tuple[bool, str]:
    if settings.llm_provider == "none":
        raise KothaError(503, "PROVIDER_NOT_CONFIGURED", "LLM provider is set to none")

    confirmed_input = "আজ তিন দিন ধরে আমার মাথায় ব্যথা ও অল্প জ্বর আছে।"
    res = await extract(confirmed_input, settings)
    if not res.chief_complaint or res.chief_complaint.status not in ("reported", "uncertain"):
        raise RuntimeError("Clinical extraction failed to produce valid chief_complaint")
    return True, f"extraction status={res.chief_complaint.status}"


async def check_tts(settings: Settings) -> tuple[bool, str]:
    if settings.tts_provider == "none":
        raise KothaError(503, "PROVIDER_NOT_CONFIGURED", "TTS provider is set to none")

    tts = get_tts_provider(settings)
    template_text = build_spoken_template_text(has_urgent_or_emergency=False, uncertain_or_missing=[])
    audio_bytes, mime = await tts.synthesize(template_text)
    if not audio_bytes or len(audio_bytes) < 100:
        raise RuntimeError("TTS returned empty or invalid audio stream")
    return True, f"provider={tts.name}, bytes={len(audio_bytes)}"


async def main() -> int:
    settings = get_settings()
    steps = [
        ("(a) ffmpeg present", check_ffmpeg, False),
        ("(b) STT: transcribe demo_assets/audio/sample_A.wav", check_stt, True),
        ("(c) LLM: normalize a verified glossary sentence", check_normalization, True),
        ("(d) LLM: extract structured info from confirmed text", check_extraction, True),
        ("(e) TTS: synthesize template reply", check_tts, True),
    ]

    all_passed = True
    print("=" * 60)
    print("Kotha Live Provider Health Check")
    print(f"App Mode: {settings.app_mode}")
    print(f"Configured Providers -> STT: {settings.speech_provider}, LLM: {settings.llm_provider}, TTS: {settings.tts_provider}")
    print("=" * 60)

    for label, fn, needs_settings in steps:
        t0 = time.perf_counter()
        try:
            if needs_settings:
                passed, detail = await fn(settings)
            else:
                passed, detail = await fn()
            elapsed = time.perf_counter() - t0
            print(f"[PASS] {label} ({elapsed:.3f}s)")
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            all_passed = False
            err_sanitized = _sanitize_error(exc)
            print(f"[FAIL] {label} ({elapsed:.3f}s) - {err_sanitized}")

    print("=" * 60)
    if all_passed:
        print("ALL PROVIDERS PASSED (exit code 0)")
        return 0
    else:
        print("ONE OR MORE PROVIDERS FAILED (exit code 1)")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
