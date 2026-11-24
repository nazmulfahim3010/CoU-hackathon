"""Speech-to-text service with provider adapters and ffmpeg audio preprocessing.

Enforces zero-storage guarantees: all audio transcoding happens in ephemeral temp files
that are strictly cleaned up inside `finally` blocks.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import unicodedata
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

# Defaults per provider. hf-inference answers "Model not supported by provider hf-inference" (HTTP 400) for
# BanglaASR, whisper-small/base/tiny; whisper-large-v3 IS served but the HF account needs pre-paid credits (402).
HF_DEFAULT_MODEL = "openai/whisper-large-v3"
LOCAL_DEFAULT_MODEL = "openai/whisper-tiny"

_SECRET_RE = re.compile(r"(?:gsk_|sk-[A-Za-z0-9]*-?|hf_|AQ\.|Bearer\s+)[A-Za-z0-9_\-\.]{8,}")


def effective_speech_model(s: Settings) -> str:
    """The model id actually sent. An explicit SPEECH_MODEL always wins; otherwise a default that exists on the
    configured provider (Groq: whisper-large-v3, OpenAI: whisper-1, Hugging Face: openai/whisper-large-v3)."""
    if s.speech_model:
        return s.speech_model
    if s.speech_provider == "hf_inference":
        return HF_DEFAULT_MODEL
    if s.speech_provider == "openai_compatible":
        return "whisper-large-v3" if "groq.com" in (s.speech_base_url or "").lower() else "whisper-1"
    return LOCAL_DEFAULT_MODEL


def safe_provider_hint(resp: httpx.Response, limit: int = 160) -> str:
    """A short, sanitized reason taken from a provider error body (e.g. 'Model not supported by provider
    hf-inference'). Never contains keys, auth headers or audio: only the provider's own error text, with any
    key-looking token redacted, control characters removed and length capped."""
    msg = ""
    try:
        data = resp.json()
    except ValueError:
        data = None
    if isinstance(data, dict):
        err = data.get("error", data.get("message"))
        if isinstance(err, dict):
            err = err.get("message") or err.get("code") or err.get("type")
        if isinstance(err, str):
            msg = err
    elif data is None and "text" in resp.headers.get("content-type", ""):
        msg = resp.text[: limit * 2]
    msg = _SECRET_RE.sub("<redacted>", msg)
    msg = re.sub(r"[^\S ]+|[\x00-\x1f]", " ", msg)
    msg = re.sub(r"\s+", " ", msg).strip()
    return msg[:limit]


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


_SPECIAL_TOKEN = re.compile(r"<\|[^|>]{0,40}\|>")  # Whisper control tokens that sometimes leak into text, e.g. <|sq|>
_ALLOWED_CONTROLS = "\n\t‌‍"  # line breaks, tab, ZWNJ, ZWJ (ZWNJ/ZWJ are legitimate in Bangla)
_BN_RUN = re.compile(r"[ঀ-৿‌‍]+")
_HASANTA, _NUKTA = "্", "়"
# A transcript is rejected when at least this many words, and this share of all words, cannot be Bangla words.
MIN_IMPOSSIBLE_WORDS = 2
MAX_IMPOSSIBLE_WORD_RATIO = 0.15


def _is_consonant(c: str) -> bool:
    o = ord(c) if c else 0
    return bool(c) and (0x0995 <= o <= 0x09B9 or o in (0x09CE, 0x09DC, 0x09DD, 0x09DF, 0x09F0, 0x09F1))


def _is_independent_vowel(c: str) -> bool:
    o = ord(c) if c else 0
    return 0x0985 <= o <= 0x0994 or o in (0x09E0, 0x09E1)


def _is_vowel_sign(c: str) -> bool:
    o = ord(c) if c else 0
    return 0x09BE <= o <= 0x09C4 or o in (0x09C7, 0x09C8, 0x09CB, 0x09CC, 0x09D7, 0x09E2, 0x09E3)


def is_impossible_bangla_word(word: str) -> bool:
    """True if the word breaks Bengali orthography itself (so it cannot be a real word in any dialect): an
    unassigned code point, a vowel sign that does not follow a consonant (e.g. a vowel letter + sign "এা"), a
    hasanta that does not join two consonants, or an anusvara after a hasanta. Real speech transcripts in
    Bangla script (verified on the 16 Sylheti references, standard Bangla references and 120 glossary rows)
    contain none of these."""
    prev = ""
    for i, c in enumerate(word):
        if unicodedata.category(c) == "Cn":
            return True
        if _is_vowel_sign(c):
            joined_o = prev == "ে" and c in ("া", "ৗ")  # decomposed "ো" / "ৌ"
            if not (_is_consonant(prev) or prev == _NUKTA or joined_o):
                return True
        elif c == _HASANTA:
            if not (_is_consonant(prev) or prev == _NUKTA):
                return True
            nxt = word[i + 1] if i + 1 < len(word) else ""
            if nxt and not (_is_consonant(nxt) or nxt in "‌‍"):
                return True
        elif c in "ঁংঃ":
            if prev == _HASANTA or not (_is_consonant(prev) or _is_vowel_sign(prev) or _is_independent_vowel(prev) or prev == _NUKTA):
                return True
        elif c == _NUKTA and not _is_consonant(prev):
            return True
        prev = c
    return False


def sanitize_asr_text(text: str) -> str:
    """Make a recognised transcript safe to show. Removes leaked model tokens (<|sq|>) and stray invalid code
    points, and rejects text where many words are orthographically impossible (the model hallucinated pseudo-script
    instead of words). This cannot detect well-formed but WRONG words: the patient confirmation step exists for
    that. Never logs the text."""
    t = _SPECIAL_TOKEN.sub(" ", text or "")
    words = _BN_RUN.findall(unicodedata.normalize("NFC", t))
    impossible = sum(1 for w in words if is_impossible_bangla_word(w))
    if words and impossible >= MIN_IMPOSSIBLE_WORDS and impossible / len(words) >= MAX_IMPOSSIBLE_WORD_RATIO:
        raise KothaError(
            422,
            "ASR_UNINTELLIGIBLE",
            "কথা বোঝা যায়নি, আবার বলুন বা লিখে দিন (The speech could not be understood. Please record again or type your note).",
        )
    keep = []
    for ch in t:
        cat = unicodedata.category(ch)
        if cat in ("Cn", "Co", "Cs"):  # unassigned / private-use / surrogate: not real characters
            continue
        if cat[0] == "C" and ch not in _ALLOWED_CONTROLS:
            continue
        keep.append(ch)
    return re.sub(r"[ \t]+", " ", "".join(keep)).strip()


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


def probe_audio_stream(in_path: str) -> None:
    """Probe input file using ffprobe/ffmpeg to verify it contains a valid audio stream.
    Rejects non-audio files or corrupt files with KothaError(415, 'UNSUPPORTED_AUDIO').
    """
    if shutil.which("ffprobe"):
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "json",
            in_path,
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode != 0:
                raise KothaError(415, "UNSUPPORTED_AUDIO", "The file is not a supported or valid audio format.")
            import json
            try:
                info = json.loads(res.stdout.decode("utf-8", errors="ignore"))
                streams = info.get("streams", [])
                if not streams or streams[0].get("codec_type") != "audio":
                    raise KothaError(415, "UNSUPPORTED_AUDIO", "The uploaded file contains no audio stream.")
            except (json.JSONDecodeError, KeyError):
                raise KothaError(415, "UNSUPPORTED_AUDIO", "The file is not a supported or valid audio format.")
            return
        except FileNotFoundError:
            pass

    # Fallback to probing with ffmpeg if ffprobe is unavailable
    cmd = ["ffmpeg", "-v", "error", "-i", in_path, "-vn", "-f", "null", "-"]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            raise KothaError(415, "UNSUPPORTED_AUDIO", "The file is not a supported or valid audio format.")
    except FileNotFoundError:
        raise KothaError(503, "FFMPEG_NOT_INSTALLED", "Audio processing requires ffmpeg on the server.")


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

        # Probe input file to ensure it actually contains valid audio
        probe_audio_stream(in_path)

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
            raise KothaError(415, "UNSUPPORTED_AUDIO", "Could not process audio format. Please check the file.")

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
    if isinstance(exc, KothaError):
        # Our own validation (e.g. ASR_NON_BANGLA, NO_SPEECH_DETECTED) is not a provider outage: never relabel it.
        raise exc
    if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
        raise KothaError(
            504,
            "ASR_TIMEOUT",
            "স্পিচ রিকগনিশন সার্ভার সময়মতো সাড়া দেয়নি (ASR provider timed out). অনুগ্রহ করে আবার চেষ্টা করুন বা টাইপ করুন।",
        ) from exc
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        # Provider's own error text, with keys redacted and non-text bodies (e.g. audio) ignored...
        hint = safe_provider_hint(exc.response)
        # Provider error type/code (e.g. invalid_request_error) when the body has one
        error_type = ""
        try:
            body = exc.response.json()
            err = body.get("error") if isinstance(body, dict) else None
            if isinstance(err, dict):
                error_type = str(err.get("type") or err.get("code") or "")
        except ValueError:
            pass
        # ...then restricted to a conservative character set so no user text can ride along in the reason.
        keep = r"[^a-zA-Z0-9_\-\.\:\s`]"
        error_type = re.sub(keep, "", error_type)[:40].strip()
        hint = re.sub(keep, "", hint)[:100].strip()
        detail = ": ".join(p for p in (error_type, hint) if p)
        safe_reason = f"HTTP {status}: {detail}" if detail else f"HTTP {status}"

        log.warning("stt_upstream_error provider=%s status=%s reason=%s", provider, status, safe_reason)

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
        self._model = effective_speech_model(s)
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
            text = sanitize_asr_text(text)
            validate_bangla_script(text)
            return STTResult(text=text, confidence=None, provider=self.name, model=self._model)
        except Exception as exc:
            raise_for_stt(exc, self.name)
            raise


class HFInferenceSTT:
    """Hugging Face Inference API automatic-speech-recognition endpoint."""

    name = "hf_inference"

    def __init__(self, s: Settings):
        self._model = effective_speech_model(s)
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
                text = sanitize_asr_text(text)
            validate_bangla_script(text)
        except Exception as exc:
            raise_for_stt(exc, self.name)
            raise
        return STTResult(text=text, confidence=None, provider=self.name, model=self._model)


class OpenAICompatSTT:
    """OpenAI-compatible /audio/transcriptions endpoint (OpenAI, Groq, etc.)."""

    name = "openai_compatible"

    def __init__(self, s: Settings):
        self._model = effective_speech_model(s)
        self._key = s.speech_api_key
        self._timeout = s.provider_timeout_seconds
        self._base = (s.speech_base_url or "https://api.openai.com/v1").rstrip("/")
        self._prompt = s.speech_prompt

    async def transcribe(self, audio_bytes: bytes, content_type: str = "audio/wav") -> STTResult:
        form = {"model": self._model, "language": "bn", "response_format": "json"}
        if self._prompt:
            form["prompt"] = self._prompt
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(
                    f"{self._base}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self._key}"},
                    data=form,
                    files={"file": ("recording.wav", audio_bytes, content_type or "audio/wav")},
                )
                r.raise_for_status()
                text = (r.json().get("text") or "").strip()
                text = sanitize_asr_text(text)
            validate_bangla_script(text)
        except Exception as exc:
            raise_for_stt(exc, self.name)
            raise
        return STTResult(text=text, confidence=None, provider=self.name, model=self._model)


def stt_configured(s: Settings) -> bool:
    if s.speech_provider in ("hf_inference", "openai_compatible"):
        return bool(s.speech_api_key)  # the model has a per-provider default
    if s.speech_provider == "local_transformers":
        return True
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
