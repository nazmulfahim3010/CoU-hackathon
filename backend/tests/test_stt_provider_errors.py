"""Live STT: provider 4xx errors must be actionable but safe (no keys, no audio, no transcripts, no leftover files)."""
import asyncio
import io
import json
import logging
import os
import wave

import httpx
import pytest

from app.config import Settings
from app.core.exceptions import KothaError
from app.services import speech_to_text as stt
from conftest import requires_ffmpeg

KEY = "gsk_" + "A1b2C3d4E5" * 4  # a realistic-looking secret that must never leak


def wav_bytes(seconds: float = 1.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x01" * int(16000 * seconds))
    return buf.getvalue()


@pytest.fixture
def mock_provider(monkeypatch):
    """Route every httpx.AsyncClient used by the adapters through a handler; record what was sent."""
    seen = {}

    def install(handler):
        real = httpx.AsyncClient

        def fake(*a, **kw):
            def wrapped(request: httpx.Request):
                seen["url"] = str(request.url)
                seen["headers"] = dict(request.headers)
                seen["body"] = request.content
                return handler(request)

            kw["transport"] = httpx.MockTransport(wrapped)
            return real(*a, **kw)

        monkeypatch.setattr(stt.httpx, "AsyncClient", fake)
        return seen

    return install


def groq(**over) -> Settings:
    base = dict(speech_provider="openai_compatible", speech_base_url="https://api.groq.com/openai/v1", speech_api_key=KEY)
    base.update(over)
    return Settings(**base)


def err(status: int, body):
    return lambda request: httpx.Response(status, json=body) if isinstance(body, (dict, list)) else httpx.Response(status, text=body)


# ---------- the sanitized, actionable error
def test_400_keeps_a_safe_provider_hint(mock_provider):
    mock_provider(err(400, {"error": "Model not supported by provider hf-inference"}))
    s = Settings(speech_provider="hf_inference", speech_api_key=KEY)
    with pytest.raises(KothaError) as e:
        asyncio.run(stt.HFInferenceSTT(s).transcribe(wav_bytes(), "audio/wav"))
    assert e.value.status_code == 502 and e.value.code == "PROVIDER_ERROR"
    assert "HTTP 400" in e.value.message
    assert "Model not supported by provider hf-inference" in e.value.message
    assert KEY not in e.value.message


def test_openai_style_error_object_is_understood(mock_provider):
    mock_provider(err(400, {"error": {"message": "The model `x` does not exist", "type": "invalid_request_error"}}))
    with pytest.raises(KothaError) as e:
        asyncio.run(stt.OpenAICompatSTT(groq(speech_model="x")).transcribe(wav_bytes(), "audio/wav"))
    assert "does not exist" in e.value.message


def test_quota_and_credit_errors_are_explained(mock_provider):
    mock_provider(err(429, {"error": {"message": "You have no credits remaining.", "code": "credit_balance_exhausted"}}))
    with pytest.raises(KothaError) as e:
        asyncio.run(stt.OpenAICompatSTT(groq()).transcribe(wav_bytes(), "audio/wav"))
    assert "HTTP 429" in e.value.message and "no credits remaining" in e.value.message


def test_a_provider_that_echoes_the_key_is_redacted(mock_provider):
    mock_provider(err(401, {"error": {"message": f"Invalid API key {KEY} for this request"}}))
    with pytest.raises(KothaError) as e:
        asyncio.run(stt.OpenAICompatSTT(groq()).transcribe(wav_bytes(), "audio/wav"))
    assert KEY not in e.value.message and "A1b2C3d4E5" not in e.value.message
    assert "<redacted>" in e.value.message


def test_hint_is_short_single_line_and_ignores_html_pages():
    long = httpx.Response(400, json={"error": "x" * 1000 + "\n\tline2"})
    hint = stt.safe_provider_hint(long)
    assert len(hint) <= 160 and "\n" not in hint and "\t" not in hint
    html = httpx.Response(502, text="<html><body>Bad gateway</body></html>", headers={"content-type": "text/html"})
    assert "<html" not in stt.safe_provider_hint(html) or len(stt.safe_provider_hint(html)) <= 160
    binary = httpx.Response(400, content=b"RIFF\x00\x00WAVEfmt ", headers={"content-type": "application/octet-stream"})
    assert stt.safe_provider_hint(binary) == ""  # never echoes non-text bodies (e.g. audio)


def test_non_http_failures_stay_generic(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(stt.httpx, "AsyncClient", boom)
    with pytest.raises(KothaError) as e:
        asyncio.run(stt.OpenAICompatSTT(groq()).transcribe(wav_bytes(), "audio/wav"))
    assert e.value.code == "PROVIDER_UNREACHABLE"


# ---------- request shape for Groq (OpenAI-compatible)
def test_groq_request_is_a_correct_multipart_upload(mock_provider):
    seen = mock_provider(lambda r: httpx.Response(200, json={"text": "ok"}))
    out = asyncio.run(stt.OpenAICompatSTT(groq(speech_model="whisper-large-v3")).transcribe(wav_bytes(), "audio/wav"))
    assert out.text == "ok" and out.model == "whisper-large-v3"
    assert seen["url"] == "https://api.groq.com/openai/v1/audio/transcriptions"
    assert seen["headers"]["authorization"] == f"Bearer {KEY}"
    assert seen["headers"]["content-type"].startswith("multipart/form-data")
    body = seen["body"]
    assert b'name="model"' in body and b"whisper-large-v3" in body
    assert b'name="language"' in body and b'name="file"; filename="recording.wav"' in body
    assert b"Content-Type: audio/wav" in body and body.count(b"RIFF") >= 1


# ---------- model defaults: never send one provider's model id to another
def test_settings_no_longer_default_to_the_hugging_face_model():
    assert Settings().speech_model == ""


def test_effective_model_defaults_per_provider():
    assert stt.effective_speech_model(groq()) == "whisper-large-v3"
    assert stt.effective_speech_model(Settings(speech_provider="openai_compatible")) == "whisper-1"
    assert stt.effective_speech_model(Settings(speech_provider="hf_inference")) == stt.HF_DEFAULT_MODEL
    assert stt.effective_speech_model(groq(speech_model="whisper-large-v3-turbo")) == "whisper-large-v3-turbo"  # explicit wins
    assert "BanglaASR" not in stt.effective_speech_model(Settings(speech_provider="hf_inference"))


def test_groq_without_a_model_sends_a_groq_model(mock_provider):
    seen = mock_provider(lambda r: httpx.Response(200, json={"text": "ok"}))
    asyncio.run(stt.OpenAICompatSTT(groq()).transcribe(wav_bytes(), "audio/wav"))
    assert b"whisper-large-v3" in seen["body"] and b"BanglaASR" not in seen["body"]


def test_cloud_providers_are_configured_with_just_a_key():
    assert stt.stt_configured(groq()) is True
    assert stt.stt_configured(Settings(speech_provider="openai_compatible")) is False  # no key
    assert stt.stt_configured(Settings()) is False


# ---------- full route: no leftover files, nothing sensitive logged
@requires_ffmpeg
def test_route_surfaces_hint_leaves_no_temp_files_and_logs_nothing_sensitive(client, mock_provider, monkeypatch, tmp_path, caplog):
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))  # process_audio writes its temp files here
    mock_provider(err(400, {"error": "Model not supported by provider hf-inference"}))
    adapter = stt.HFInferenceSTT(Settings(speech_provider="hf_inference", speech_api_key=KEY))
    monkeypatch.setattr("app.api.routes.transcription.get_stt", lambda s: adapter)

    with caplog.at_level(logging.DEBUG):
        r = client.post("/api/transcription", files={"audio": ("rec.wav", wav_bytes(2.0), "audio/wav")})

    assert r.status_code == 502
    msg = r.json()["error"]["message"]
    assert r.json()["error"]["code"] == "PROVIDER_ERROR"
    assert "HTTP 400" in msg and "Model not supported by provider hf-inference" in msg
    assert KEY not in json.dumps(r.json()) and KEY not in caplog.text
    assert os.listdir(tmp_path) == []  # temp audio removed even though the provider failed
    assert "RIFF" not in caplog.text


@requires_ffmpeg
def test_route_succeeds_when_the_provider_does(client, mock_provider, monkeypatch, tmp_path):
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    mock_provider(lambda r: httpx.Response(200, json={"text": "আমার মাথা ব্যথা"}))
    adapter = stt.OpenAICompatSTT(groq())
    monkeypatch.setattr("app.api.routes.transcription.get_stt", lambda s: adapter)
    r = client.post("/api/transcription", files={"audio": ("rec.wav", wav_bytes(2.0), "audio/wav")})
    assert r.status_code == 200 and r.json()["transcript"] == "আমার মাথা ব্যথা"
    assert os.listdir(tmp_path) == []
