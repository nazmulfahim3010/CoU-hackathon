import os

import pytest

from app.core.exceptions import KothaError
from app.core.session_manager import SessionManager, Stage
from app.services import text_to_speech
from conftest import demo_confirmed, demo_session


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_session_expires():
    clock = Clock()
    sm = SessionManager(60, clock=clock)
    s = sm.create("demo")
    assert sm.get(s.id)
    clock.t += 61
    with pytest.raises(KothaError) as e:
        sm.get(s.id)
    assert e.value.status_code == 404 and len(sm) == 0


def test_purge_removes_expired_data():
    clock = Clock()
    sm = SessionManager(60, clock=clock)
    s = sm.create("live")
    s.data["original"] = "sensitive"
    clock.t += 120
    assert sm.purge_expired() == 1 and len(sm) == 0


def test_session_ordering_enforced():
    sm = SessionManager(60)
    s = sm.create("demo")
    with pytest.raises(KothaError):
        sm.require(s.id, Stage.CONFIRMED)


def test_delete_endpoint_discards_data(client):
    sid = demo_session(client)
    assert client.delete(f"/api/session/{sid}").status_code == 204
    assert client.post("/api/normalization", json={"session_id": sid}).status_code == 404


def test_workflow_writes_no_files(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(text_to_speech, "_synthesize_gtts", lambda t: b"ID3fake")
    sid = demo_confirmed(client, "B_red_flag")
    client.post("/api/clinical/extract", json={"session_id": sid})
    client.post("/api/safety/evaluate", json={"session_id": sid})
    client.post("/api/summary/generate", json={"session_id": sid})
    client.post("/api/speech/generate", json={"session_id": sid})
    assert os.listdir(tmp_path) == []


def run_full(client, scenario):
    sid = demo_confirmed(client, scenario)
    ext = client.post("/api/clinical/extract", json={"session_id": sid})
    saf = client.post("/api/safety/evaluate", json={"session_id": sid})
    summ = client.post("/api/summary/generate", json={"session_id": sid})
    assert ext.status_code == saf.status_code == summ.status_code == 200
    return sid, saf.json(), summ.json()


@pytest.mark.parametrize("scenario,expected", [
    ("A_ordinary", set()),
    ("B_red_flag", {"CHEST_PAIN", "BREATHING_DIFFICULTY"}),
    ("C_uncertain", set()),
])
def test_demo_scenarios_end_to_end(client, monkeypatch, scenario, expected):
    monkeypatch.setattr(text_to_speech, "_synthesize_gtts", lambda t: b"ID3fake")
    sid, saf, summ = run_full(client, scenario)
    assert {r["rule_id"] for r in saf["triggered"]} == expected
    assert {r["rule_id"] for r in summ["red_flags"]} == expected
    assert "verification required" in summ["label_en"]
    assert "not a diagnostic tool" in summ["disclaimer_en"]
    assert summ["provenance"]["speech_to_text"] in ("demo_prepared_text", "demo_sample")
    assert summ["provenance"]["red_flags"] == "deterministic rules"
    assert summ["original_statement"] and summ["normalized_statement"]
    keys = [s["key"] for s in summ["sections"]]
    assert keys[:4] == ["chief_complaint", "symptoms", "duration", "severity"]
    sp = client.post("/api/speech/generate", json={"session_id": sid}).json()
    assert sp["audio_base64"] and sp["text_bn"]
    assert ("জরুরি" in sp["text_bn"]) == bool(expected)
    assert "রোগ নির্ণয় নয়" in sp["text_bn"]


def test_uncertain_scenario_summary_does_not_claim_absence(client):
    _, _, summ = run_full(client, "C_uncertain")
    sev = next(s for s in summ["sections"] if s["key"] == "severity")
    assert sev["en"] == ["Not reported"]
    neg = next(s for s in summ["sections"] if s["key"] == "negatives")
    assert neg["en"] == ["None explicitly stated"]


def test_tts_failure_is_reported_not_faked(client, monkeypatch):
    def boom(t):
        raise RuntimeError("network down")
    monkeypatch.setattr(text_to_speech, "_synthesize_gtts", boom)
    sid, _, _ = run_full(client, "A_ordinary")
    r = client.post("/api/speech/generate", json={"session_id": sid})
    assert r.status_code == 503 and r.json()["error"]["code"] == "TTS_FAILED"
    assert client.get(f"/api/speech/text/{sid}").json()["text_bn"]


def test_summary_requires_extraction_and_safety(client):
    sid = demo_confirmed(client, "A_ordinary")
    assert client.post("/api/summary/generate", json={"session_id": sid}).status_code == 409
    client.post("/api/safety/evaluate", json={"session_id": sid})
    assert client.post("/api/summary/generate", json={"session_id": sid}).status_code == 409
