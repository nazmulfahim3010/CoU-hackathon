import json
import os
import tempfile
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # portable: works on any machine and in Docker

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import KothaError
from app.core.session_manager import Stage
from app.main import app
from app.services.speech_to_text import STTResult, process_audio
from conftest import WEBM, FakeSTT, demo_session

client = TestClient(app)


def make_test_wav(duration_seconds: float = 1.0) -> bytes:
    """Generate in-memory valid 16kHz mono 16-bit WAV bytes."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    try:
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            n_frames = int(16000 * duration_seconds)
            # Write silence / basic audio tone frames
            wf.writeframes(b"\x00\x00" * n_frames)
        return Path(path).read_bytes()
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_invalid_file_type_is_415():
    r = client.post("/api/transcription", files={"audio": ("bad.bin", b"not-audio" * 200, "application/octet-stream")})
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "INVALID_AUDIO"


def test_empty_audio_is_400():
    r = client.post("/api/transcription", files={"audio": ("empty.wav", b"", "audio/wav")})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "EMPTY_AUDIO"


def test_oversized_audio_is_413():
    # Audio exceeding max_bytes limit (10MB default)
    r = client.post(
        "/api/transcription",
        files={"audio": ("huge.wav", b"RIFF" + b"\x00" * (11 * 1024 * 1024), "audio/wav")},
    )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "AUDIO_TOO_LARGE"


def test_audio_longer_than_90s_rejected():
    long_wav = make_test_wav(duration_seconds=92.0)
    with pytest.raises(KothaError) as exc_info:
        process_audio(long_wav, max_bytes=20 * 1024 * 1024)
    assert exc_info.value.status_code == 413
    assert exc_info.value.code == "AUDIO_TOO_LONG"


def test_temp_files_deleted_after_success_and_failure(monkeypatch):
    """Zero-storage guarantee: asserts no temporary files remain in temp directory."""
    temp_dir = tempfile.gettempdir()
    before_files = set(os.listdir(temp_dir))

    wav_bytes = make_test_wav(duration_seconds=2.0)

    # 1. Test deletion on SUCCESS
    proc_bytes, duration = process_audio(wav_bytes, max_bytes=10 * 1024 * 1024)
    assert len(proc_bytes) > 0
    assert duration > 1.9
    after_success_files = set(os.listdir(temp_dir))
    new_after_success = [f for f in after_success_files - before_files if f.endswith(".raw") or "_converted.wav" in f]
    assert new_after_success == []

    # 2. Test deletion on FAILURE (e.g. ffmpeg conversion failure or empty wave)
    silent_wav = make_test_wav(duration_seconds=0.0)
    with pytest.raises(KothaError):
        process_audio(silent_wav, max_bytes=10 * 1024 * 1024)
    after_failure_files = set(os.listdir(temp_dir))
    new_after_failure = [f for f in after_failure_files - before_files if f.endswith(".raw") or "_converted.wav" in f]
    assert new_after_failure == []


def test_wrong_session_state_returns_409(monkeypatch):
    # Create session and move to NORMALIZED
    sid = demo_session(client, "A_ordinary")
    client.post("/api/normalization", json={"session_id": sid})

    # Calling transcription on a NORMALIZED session must return 409
    wav_bytes = make_test_wav(duration_seconds=1.0)
    r = client.post(
        "/api/transcription",
        data={"session_id": sid},
        files={"audio": ("test.wav", wav_bytes, "audio/wav")},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "WORKFLOW_ORDER_VIOLATION"


def test_provider_failure_returns_502_no_fake_transcript(monkeypatch):
    class FailingSTT:
        name = "failing"
        async def transcribe(self, audio_bytes, content_type="audio/wav"):
            raise KothaError(502, "PROVIDER_ERROR", "Speech service unavailable.")

    monkeypatch.setattr("app.api.routes.transcription.get_stt", lambda s: FailingSTT())
    wav_bytes = make_test_wav(duration_seconds=1.0)
    r = client.post(
        "/api/transcription",
        files={"audio": ("test.wav", wav_bytes, "audio/wav")},
    )
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "PROVIDER_ERROR"
    # Guaranteed: no fake text returned on failure
    assert "transcript" not in r.json()


def test_transcription_typed_endpoint():
    # 1. Create a session via POST /api/session
    res = client.post("/api/session", json={"mode": "live"})
    sid = res.json()["session_id"]

    # 2. Post manual typed transcript
    typed_payload = {
        "session_id": sid,
        "text": "আইজ তিন দিন ধরি মোর মাতাত ব্যতা",
        "dialect_hint": "sylheti",
    }
    r = client.post("/api/transcription/typed", json=typed_payload)
    assert r.status_code == 200
    data = r.json()
    assert data["session_id"] == sid
    assert data["transcript"] == "আইজ তিন দিন ধরি মোর মাতাত ব্যতা"
    assert data["source"] == "typed_by_user"
    assert data["provider"] == "manual"
    assert data["confidence"] == 1.0


def test_real_audio_transcription_comparison(monkeypatch):
    """Run real audio file from demo_assets/audio through processing pipeline."""
    audio_path = REPO_ROOT / "demo_assets" / "audio" / "sample_A.wav"
    assert audio_path.exists(), "demo_assets audio file must exist"
    audio_bytes = audio_path.read_bytes()

    # Load sample transcript
    transcripts_path = REPO_ROOT / "demo_assets" / "transcripts.json"
    with open(transcripts_path, encoding="utf-8") as f:
        meta = json.load(f)[0]

    sample_orig = meta["original_transcript"]
    sample_std = meta["standard_bangla"]

    # Process audio via process_audio to verify ffmpeg 16kHz mono conversion & duration
    wav_proc, duration = process_audio(audio_bytes, max_bytes=10 * 1024 * 1024)
    assert duration > 5.0 and duration < 20.0

    # With mocked ASR returning candidate output to test API response shape
    mock_asr_text = sample_orig  # stands in for ASR output; real recognition is not exercised here
    monkeypatch.setattr("app.api.routes.transcription.get_stt", lambda s: FakeSTT(mock_asr_text))

    r = client.post(
        "/api/transcription",
        files={"audio": ("sample_A.wav", audio_bytes, "audio/wav")},
    )
    assert r.status_code == 200
    res = r.json()
    assert res["source"] in ("speech_recognition", "speech_model")
    assert res["duration_seconds"] > 5.0
    assert res["transcript"] == mock_asr_text
