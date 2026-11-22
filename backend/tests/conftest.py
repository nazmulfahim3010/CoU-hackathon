import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings, get_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.providers.stt import STTResult  # noqa: E402

WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 2000


class FakeLLM:
    """Scripted LLM: returns queued replies in order, then repeats the last one."""

    name = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    async def complete(self, system, user, max_tokens=1500):
        self.calls += 1
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]


class FakeSTT:
    name = "fake_stt"

    def __init__(self, text):
        self.text = text

    async def transcribe(self, audio, content_type):
        return STTResult(self.text, None, "fake_stt", "fake-model")


@pytest.fixture
def settings():
    return Settings(speech_provider="none", llm_provider="none", tts_provider="gtts")


@pytest.fixture
def client(settings):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def demo_session(client, scenario="A_ordinary"):
    r = client.post("/api/transcription", data={"demo_scenario_id": scenario})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def demo_confirmed(client, scenario="A_ordinary", edit=None):
    sid = demo_session(client, scenario)
    n = client.post("/api/normalization", json={"session_id": sid}).json()
    c = client.post("/api/confirmation", json={
        "session_id": sid, "original_text": n["original"],
        "confirmed_text": edit or n["normalized"], "confirmed": True})
    assert c.status_code == 200, c.text
    return sid


def valid_extraction_json(**over):
    base = {
        "chief_complaint": {"status": "reported", "bn": "জ্বর", "en": "Fever"},
        "symptoms": [{"bn": "জ্বর", "en": "Fever"}],
        "duration": {"status": "reported", "bn": "তিন দিন", "en": "Three days"},
        "severity": {"status": "not_reported"},
        "relevant_history": {"status": "not_reported"},
        "current_medications": {"status": "not_reported"},
        "allergies": {"status": "not_reported"},
        "associated_symptoms": [], "negative_symptoms": [], "uncertain_or_missing": [],
        "model_noted_red_flag_indicators": [],
    }
    base.update(over)
    return json.dumps(base, ensure_ascii=False)
