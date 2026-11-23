import pytest

from app.core.exceptions import KothaError
from app.core.security import validate_audio
from conftest import WEBM, FakeSTT, requires_ffmpeg


def test_validate_audio_rejects_bad_input():
    with pytest.raises(KothaError) as e:
        validate_audio(b"", 1000)
    assert e.value.code == "EMPTY_AUDIO"
    with pytest.raises(KothaError) as e:
        validate_audio(b"abc", 1000)
    assert e.value.code == "AUDIO_TOO_SHORT"
    with pytest.raises(KothaError) as e:
        validate_audio(WEBM, 500)
    assert e.value.status_code == 413
    with pytest.raises(KothaError) as e:
        validate_audio(b"this is not audio" * 200, 10_000)
    assert e.value.status_code == 415


def test_validate_audio_accepts_webm():
    assert validate_audio(WEBM, 100_000) == "webm/matroska"


def test_upload_invalid_file_is_415(client):
    r = client.post("/api/transcription", files={"audio": ("x.webm", b"hello" * 500, "audio/webm")})
    assert r.status_code == 415


def test_upload_empty_is_400(client):
    r = client.post("/api/transcription", files={"audio": ("x.webm", b"", "audio/webm")})
    assert r.status_code == 400


def test_no_input_is_400(client):
    assert client.post("/api/transcription").status_code == 400


def test_live_without_provider_is_503_not_fake_output(client):
    r = client.post("/api/transcription", files={"audio": ("x.webm", WEBM, "audio/webm")})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "PROVIDER_NOT_CONFIGURED"


@requires_ffmpeg
def test_live_transcription_ok(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.transcription.get_stt", lambda s: FakeSTT("আইজ জ্বর"))
    r = client.post("/api/transcription", files={"audio": ("x.webm", WEBM, "audio/webm")})
    body = r.json()
    assert r.status_code == 200
    assert body["mode"] == "live" and body["source"] in ("speech_recognition", "speech_model")
    assert body["confidence"] is None  # never invented
    assert body["transcript"] == "আইজ জ্বর"


@requires_ffmpeg
def test_blank_transcript_is_422(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.transcription.get_stt", lambda s: FakeSTT("   "))
    r = client.post("/api/transcription", files={"audio": ("x.webm", WEBM, "audio/webm")})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "NO_SPEECH_DETECTED"


def test_demo_is_labelled_not_speech_recognition(client):
    body = client.post("/api/transcription", data={"demo_scenario_id": "A_ordinary"}).json()
    assert body["mode"] == "demo" and body["source"] in ("demo_prepared_text", "demo_sample")
    assert "NOT" in body["disclaimer"]


def test_unknown_demo_scenario_404(client):
    assert client.post("/api/transcription", data={"demo_scenario_id": "nope"}).status_code == 404


def test_health_exposes_no_secrets(client):
    body = client.get("/api/health").text
    assert "api_key" not in body.lower()
