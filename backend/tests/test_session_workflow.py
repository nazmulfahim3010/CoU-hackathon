import uuid

import pytest

from app.core.exceptions import KothaError
from app.core.session_manager import SessionManager, Stage
from conftest import demo_confirmed, demo_session


class MockClock:
    def __init__(self, start: float = 1000.0):
        self.time = start

    def __call__(self) -> float:
        return self.time


def test_create_session_endpoint(client):
    res = client.post("/api/session", json={"mode": "live"})
    assert res.status_code == 201
    data = res.json()
    assert "session_id" in data
    # Verify UUID4 format
    parsed_uuid = uuid.UUID(data["session_id"], version=4)
    assert str(parsed_uuid) == data["session_id"]
    assert data["state"] == "CREATED"
    assert data["mode"] == "live"
    assert data["expires_at"] > 0


def test_extraction_safety_summary_blocked_before_confirmed(client):
    res = client.post("/api/session", json={"mode": "live"})
    sid = res.json()["session_id"]

    # When state is CREATED
    assert client.post("/api/clinical/extract", json={"session_id": sid}).status_code == 409
    assert client.post("/api/safety/evaluate", json={"session_id": sid}).status_code == 409
    assert client.post("/api/summary/generate", json={"session_id": sid}).status_code == 409

    # Now transition to TRANSCRIBED via demo transcription
    sid2 = demo_session(client, "A_ordinary")
    assert client.post("/api/clinical/extract", json={"session_id": sid2}).status_code == 409
    assert client.post("/api/safety/evaluate", json={"session_id": sid2}).status_code == 409
    assert client.post("/api/summary/generate", json={"session_id": sid2}).status_code == 409

    # Now transition to NORMALIZED
    client.post("/api/normalization", json={"session_id": sid2})
    r_extract = client.post("/api/clinical/extract", json={"session_id": sid2})
    assert r_extract.status_code == 409
    assert r_extract.json()["error"]["code"] == "CONFIRMATION_REQUIRED"
    assert client.post("/api/safety/evaluate", json={"session_id": sid2}).status_code == 409
    assert client.post("/api/summary/generate", json={"session_id": sid2}).status_code == 409


def test_skipping_states_is_impossible(client):
    res = client.post("/api/session", json={"mode": "live"})
    sid = res.json()["session_id"]

    # State is CREATED; cannot skip directly to NORMALIZED without TRANSCRIBED
    r_norm = client.post("/api/normalization", json={"session_id": sid})
    assert r_norm.status_code == 409
    assert r_norm.json()["error"]["code"] == "WORKFLOW_ORDER_VIOLATION"

    # Cannot skip directly to CONFIRMED without NORMALIZED
    r_conf = client.post(
        "/api/confirmation",
        json={"session_id": sid, "original_text": "x", "confirmed_text": "x", "confirmed": True},
    )
    assert r_conf.status_code == 409
    assert r_conf.json()["error"]["code"] == "WORKFLOW_ORDER_VIOLATION"


def test_require_state_helper():
    clock = MockClock()
    sm = SessionManager(ttl_seconds=1800, clock=clock)
    s = sm.create("live")
    assert s.stage == Stage.CREATED

    # require_state allows CREATED
    assert sm.require_state(s.id, [Stage.CREATED]) == s

    # require_state rejects when stage is not in allowed
    with pytest.raises(KothaError) as exc_info:
        sm.require_state(s.id, [Stage.CONFIRMED])
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "CONFIRMATION_REQUIRED"

    # require_state rejects non-confirmed future stages with WORKFLOW_ORDER_VIOLATION
    with pytest.raises(KothaError) as exc_info2:
        sm.require_state(s.id, [Stage.TRANSCRIBED])
    assert exc_info2.value.status_code == 409
    assert exc_info2.value.code == "WORKFLOW_ORDER_VIOLATION"


def test_editing_after_confirmation_removes_confirmed(client):
    sid = demo_confirmed(client, "A_ordinary")

    # Run extraction and safety in confirmed state
    assert client.post("/api/clinical/extract", json={"session_id": sid}).status_code == 200
    assert client.post("/api/safety/evaluate", json={"session_id": sid}).status_code == 200

    # Patient edits confirmed text
    norm_res = client.post("/api/normalization", json={"session_id": sid}).json()
    conf_res = client.post(
        "/api/confirmation",
        json={
            "session_id": sid,
            "original_text": norm_res["original"],
            "confirmed_text": "আজ মাথা খুব ব্যথা",
            "confirmed": True,
        },
    ).json()
    assert conf_res["edited_by_patient"] is True

    # Re-confirmation invalidates downstream extracted and summary state
    # Calling summary now fails because extraction must be re-run on the newly edited confirmed text
    assert client.post("/api/summary/generate", json={"session_id": sid}).status_code == 409


def test_re_recording_resets_session():
    clock = MockClock()
    sm = SessionManager(ttl_seconds=1800, clock=clock)
    s = sm.create("live")
    s.stage = Stage.CONFIRMED
    s.original_transcript = "orig"
    s.confirmed_text = "conf"
    s.data["extra"] = "val"

    s.reset_to_created()
    assert s.stage == Stage.CREATED
    assert s.original_transcript == ""
    assert s.confirmed_text == ""
    assert len(s.data) == 0


def test_expired_session_returns_404_and_purges(client):
    clock = MockClock(start=1000.0)
    sm = SessionManager(ttl_seconds=60, clock=clock)
    s = sm.create("live")
    s.data["sensitive"] = "patient note"
    assert sm.get(s.id) == s

    # Advance time past TTL
    clock.time += 61.0

    # get raises 404
    with pytest.raises(KothaError) as exc:
        sm.get(s.id)
    assert exc.value.status_code == 404

    # Memory is cleared
    assert len(sm) == 0
    assert s.id not in sm._sessions


def test_delete_wipes_session(client):
    res = client.post("/api/session", json={"mode": "live"})
    sid = res.json()["session_id"]

    del_res = client.delete(f"/api/session/{sid}")
    assert del_res.status_code == 204

    # Confirm session is deleted from memory
    get_res = client.post("/api/normalization", json={"session_id": sid})
    assert get_res.status_code == 404


def test_purge_removes_expired_data():
    clock = MockClock()
    sm = SessionManager(60, clock=clock)
    s = sm.create("live")
    s.data["original"] = "sensitive"
    clock.time += 120
    assert sm.purge_expired() == 1 and len(sm) == 0


def test_session_ordering_enforced():
    sm = SessionManager(60)
    s = sm.create("demo")
    with pytest.raises(KothaError):
        sm.require(s.id, Stage.CONFIRMED)


def test_summary_requires_extraction_and_safety(client):
    sid = demo_confirmed(client, "A_ordinary")
    assert client.post("/api/summary/generate", json={"session_id": sid}).status_code == 409
    client.post("/api/safety/evaluate", json={"session_id": sid})
    assert client.post("/api/summary/generate", json={"session_id": sid}).status_code == 409
