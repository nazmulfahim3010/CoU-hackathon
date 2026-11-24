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
from conftest import WEBM, FakeSTT, demo_session, requires_ffmpeg

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


@requires_ffmpeg
def test_audio_longer_than_90s_rejected():
    long_wav = make_test_wav(duration_seconds=92.0)
    with pytest.raises(KothaError) as exc_info:
        process_audio(long_wav, max_bytes=20 * 1024 * 1024)
    assert exc_info.value.status_code == 413
    assert exc_info.value.code == "AUDIO_TOO_LONG"


@requires_ffmpeg
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


@requires_ffmpeg
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


@requires_ffmpeg
def test_real_audio_transcription_comparison(monkeypatch):
    """Run real audio file from demo_assets/audio through processing pipeline."""
    demo_assets_dir = Path(__file__).resolve().parents[2] / "demo_assets"
    audio_path = demo_assets_dir / "audio" / "sample_A.wav"
    assert audio_path.exists(), "demo_assets audio file must exist"
    audio_bytes = audio_path.read_bytes()

    # Load sample transcript
    transcripts_path = demo_assets_dir / "transcripts.json"
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


def test_process_audio_without_ffmpeg_raises_503_no_temp_files(monkeypatch):
    """When ffmpeg is missing, process_audio raises 503 FFMPEG_NOT_INSTALLED
    BEFORE creating any temporary file."""
    import shutil
    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    temp_dir = tempfile.gettempdir()
    before_files = set(os.listdir(temp_dir))

    with pytest.raises(KothaError) as exc_info:
        process_audio(WEBM, 100_000)

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "FFMPEG_NOT_INSTALLED"
    assert "ffmpeg" in exc_info.value.message.lower()

    after_files = set(os.listdir(temp_dir))
    new_files = [f for f in after_files - before_files if f.endswith(".raw") or "_converted.wav" in f]
    assert new_files == []


def test_transcription_endpoint_without_ffmpeg_returns_503(monkeypatch):
    """Audio upload when ffmpeg is missing returns a clean 503 JSON response
    with FFMPEG_NOT_INSTALLED code, not an unhandled 500 traceback."""
    import shutil
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    monkeypatch.setattr("app.api.routes.transcription.get_stt", lambda s: FakeSTT("test"))

    temp_dir = tempfile.gettempdir()
    before_files = set(os.listdir(temp_dir))

    r = client.post("/api/transcription", files={"audio": ("sample.webm", WEBM, "audio/webm")})
    assert r.status_code == 503
    data = r.json()
    assert "error" in data
    assert data["error"]["code"] == "FFMPEG_NOT_INSTALLED"

    after_files = set(os.listdir(temp_dir))
    new_files = [f for f in after_files - before_files if f.endswith(".raw") or "_converted.wav" in f]
    assert new_files == []


def test_validate_bangla_script_deterministic():
    """Deterministic script check rejects transcripts where <50% of letters are Bangla script."""
    from app.services.speech_to_text import validate_bangla_script

    # Latin hallucination (e.g. Icelandic misclassification from zero-shot Whisper)
    with pytest.raises(KothaError) as exc_info:
        validate_bangla_script("Ánvar fyrirðu röddina hóður.")
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "ASR_NON_BANGLA"
    assert "কথা বোঝা যায়নি" in exc_info.value.message

    # Pure English
    with pytest.raises(KothaError) as exc_info:
        validate_bangla_script("The patient reports acute chest pain and shortness of breath.")
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "ASR_NON_BANGLA"

    # Empty / whitespace
    with pytest.raises(KothaError) as exc_info:
        validate_bangla_script("   ")
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "NO_SPEECH_DETECTED"

    # Clean Bangla: passes without raising
    validate_bangla_script("আমার মাথা ব্যথা করছে এবং অল্প জ্বর আছে।")
    validate_bangla_script("৩ দিন থাকি আমার জ্বর আর সর্দি কমের না।")

    # Mixed with acronym/loanword but predominantly Bangla (>50% Bangla): passes
    validate_bangla_script("ডাক্তারবাবু একটা ECG টেস্ট করতে বলেছেন।")


def test_stt_providers_force_language_and_task(monkeypatch):
    """STT adapters must explicitly force language='bn' and task='transcribe'."""
    from app.config import Settings
    from app.services.speech_to_text import HFInferenceSTT, LocalTransformersSTT, OpenAICompatSTT

    s = Settings(
        speech_provider="local_transformers",
        speech_model="openai/whisper-tiny",
        speech_api_key="test-key",
    )

    # 1. LocalTransformersSTT
    lt = LocalTransformersSTT(s)
    captured_kwargs = {}

    class DummyPipe:
        def __call__(self, audio, generate_kwargs=None):
            captured_kwargs.update(generate_kwargs or {})
            return {"text": "আমার জ্বর আছে"}

    lt._pipeline = DummyPipe()
    import asyncio
    res = asyncio.run(lt.transcribe(b"dummy_wav"))
    assert captured_kwargs.get("language") == "bn"
    assert captured_kwargs.get("task") == "transcribe"
    assert res.text == "আমার জ্বর আছে"

    # 2. HFInferenceSTT
    hf = HFInferenceSTT(s)
    captured_hf = {}

    class DummyHFClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, headers=None, params=None, content=None):
            captured_hf["params"] = params
            captured_hf["headers"] = headers

            class DummyResp:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"text": "আমার জ্বর আছে"}

            return DummyResp()

    monkeypatch.setattr("httpx.AsyncClient", DummyHFClient)
    res_hf = asyncio.run(hf.transcribe(b"dummy_wav"))
    assert captured_hf["params"]["language"] == "bn"
    assert captured_hf["params"]["task"] == "transcribe"
    assert res_hf.text == "আমার জ্বর আছে"

    # 3. OpenAICompatSTT
    oai = OpenAICompatSTT(s)
    captured_oai = {}

    class DummyOAIClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, headers=None, data=None, files=None):
            captured_oai["data"] = data

            class DummyResp:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"text": "আমার জ্বর আছে"}

            return DummyResp()

    monkeypatch.setattr("httpx.AsyncClient", DummyOAIClient)
    res_oai = asyncio.run(oai.transcribe(b"dummy_wav"))
    assert captured_oai["data"]["language"] == "bn"
    assert "task" not in captured_oai["data"]  # task param causes HTTP 400 on Groq/OpenAI transcriptions
    assert res_oai.text == "আমার জ্বর আছে"


@requires_ffmpeg
def test_transcription_endpoint_rejects_non_bangla_hallucination(monkeypatch):
    """When ASR returns non-Bangla (e.g. Latin script), endpoint returns 422 ASR_NON_BANGLA,
    session stage remains CREATED, and transcript is never stored or presented as speech output."""
    sess_res = client.post("/api/session", json={"mode": "live"})
    sid = sess_res.json()["session_id"]

    # Mock STT to return Latin hallucination text
    monkeypatch.setattr("app.api.routes.transcription.get_stt", lambda s: FakeSTT("Ánvar fyrirðu röddina hóður."))

    test_wav = make_test_wav(1.0)
    r = client.post(
        "/api/transcription",
        data={"session_id": sid},
        files={"audio": ("speech.wav", test_wav, "audio/wav")},
    )

    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "ASR_NON_BANGLA"
    assert "কথা বোঝা যায়নি" in err["message"]

    # Session stage must NOT advance to TRANSCRIBED
    sm = app.state.sessions
    session = sm.get(sid)
    assert session.stage == Stage.CREATED
    assert not session.original_transcript


@requires_ffmpeg
def test_stt_provider_error_mapping_and_temp_cleanup(monkeypatch):
    """Test with mocked provider returning 400, 500, and timeout.
    Asserts distinct error codes (ASR_PROVIDER_REJECTED, ASR_PROVIDER_UNAVAILABLE, ASR_TIMEOUT),
    temp files are strictly deleted, and no fake transcript is returned.
    """
    import httpx
    from app.services.speech_to_text import raise_for_stt

    # 1. Direct raise_for_stt error code mapping tests
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/audio/transcriptions")
    resp_400 = httpx.Response(400, request=req, json={"error": {"type": "invalid_request_error", "message": "unknown param `task`"}})
    err_400 = httpx.HTTPStatusError("Bad Request", request=req, response=resp_400)
    with pytest.raises(KothaError) as exc_400:
        raise_for_stt(err_400, "openai_compatible")
    assert exc_400.value.code == "ASR_PROVIDER_REJECTED"
    assert exc_400.value.status_code == 502
    assert "invalid_request_error" in exc_400.value.message

    resp_500 = httpx.Response(500, request=req, json={"error": {"type": "server_error", "message": "Internal error"}})
    err_500 = httpx.HTTPStatusError("Internal Error", request=req, response=resp_500)
    with pytest.raises(KothaError) as exc_500:
        raise_for_stt(err_500, "openai_compatible")
    assert exc_500.value.code == "ASR_PROVIDER_UNAVAILABLE"
    assert exc_500.value.status_code == 502

    timeout_exc = httpx.TimeoutException("Read timed out")
    with pytest.raises(KothaError) as exc_tout:
        raise_for_stt(timeout_exc, "openai_compatible")
    assert exc_tout.value.code == "ASR_TIMEOUT"
    assert exc_tout.value.status_code == 504

    # 2. End-to-end endpoint test verifying temp file cleanup on provider 400/500/timeout
    temp_dir = tempfile.gettempdir()
    for status_or_timeout, expected_code in [
        (400, "ASR_PROVIDER_REJECTED"),
        (500, "ASR_PROVIDER_UNAVAILABLE"),
        ("timeout", "ASR_TIMEOUT"),
    ]:
        class FailingSTT:
            name = "mock_failing_stt"
            async def transcribe(self, audio_bytes, content_type="audio/wav"):
                if status_or_timeout == "timeout":
                    raise_for_stt(httpx.TimeoutException("Mock timeout"), self.name)
                elif status_or_timeout == 400:
                    resp = httpx.Response(400, request=req, json={"error": {"type": "invalid_request_error", "message": "unknown param"}})
                    raise_for_stt(httpx.HTTPStatusError("Bad Request", request=req, response=resp), self.name)
                else:
                    resp = httpx.Response(500, request=req, json={"error": {"type": "server_error"}})
                    raise_for_stt(httpx.HTTPStatusError("Server Error", request=req, response=resp), self.name)

        monkeypatch.setattr("app.api.routes.transcription.get_stt", lambda s: FailingSTT())

        before_files = set(os.listdir(temp_dir))
        test_wav = make_test_wav(1.0)
        r = client.post("/api/transcription", files={"audio": ("sample.wav", test_wav, "audio/wav")})
        assert r.status_code in (502, 504)
        data = r.json()
        assert data["error"]["code"] == expected_code
        assert "transcript" not in data  # Never return a fake transcript

        after_files = set(os.listdir(temp_dir))
        new_files = [f for f in after_files - before_files if f.endswith(".raw") or "_converted.wav" in f]
        assert new_files == []
