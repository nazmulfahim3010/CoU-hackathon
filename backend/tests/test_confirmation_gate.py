from conftest import demo_confirmed, demo_session


def test_extraction_blocked_before_normalization_and_confirmation(client):
    sid = demo_session(client)
    r = client.post("/api/clinical/extract", json={"session_id": sid})
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFIRMATION_REQUIRED"


def test_extraction_blocked_after_normalization_but_before_confirmation(client):
    sid = demo_session(client)
    client.post("/api/normalization", json={"session_id": sid})
    r = client.post("/api/clinical/extract", json={"session_id": sid})
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFIRMATION_REQUIRED"


def test_all_downstream_endpoints_blocked_without_confirmation(client):
    sid = demo_session(client)
    client.post("/api/normalization", json={"session_id": sid})
    for path in ("/api/safety/evaluate", "/api/summary/generate", "/api/speech/generate"):
        assert client.post(path, json={"session_id": sid}).status_code == 409, path


def test_confirmation_requires_confirmed_true(client):
    sid = demo_session(client)
    n = client.post("/api/normalization", json={"session_id": sid}).json()
    r = client.post("/api/confirmation", json={"session_id": sid, "original_text": n["original"],
                                               "confirmed_text": n["normalized"], "confirmed": False})
    assert r.status_code == 400
    assert client.post("/api/clinical/extract", json={"session_id": sid}).status_code == 409


def test_confirmation_requires_normalization_first(client):
    sid = demo_session(client)
    r = client.post("/api/confirmation", json={"session_id": sid, "original_text": "x",
                                               "confirmed_text": "x", "confirmed": True})
    assert r.status_code == 409


def test_confirmation_happy_path(client):
    sid = demo_session(client)
    n = client.post("/api/normalization", json={"session_id": sid}).json()
    r = client.post(
        "/api/confirmation",
        json={
            "session_id": sid,
            "confirmed_text": n["normalized"],
            "edited": False,
            "confirmed_by": "patient",
        },
    )
    assert r.status_code == 200
    res = r.json()
    assert res["stage"] == "confirmed"
    assert res["confirmed_by"] == "patient"
    assert res["confirmed_text"] == n["normalized"]
    assert res["edited_by_patient"] is False


def test_empty_confirmed_text_rejected(client):
    sid = demo_session(client)
    client.post("/api/normalization", json={"session_id": sid})
    r = client.post(
        "/api/confirmation",
        json={
            "session_id": sid,
            "confirmed_text": "   ",
            "confirmed": True,
        },
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "EMPTY_TEXT"


def test_confirm_twice_behaves_correctly(client):
    sid = demo_session(client)
    n = client.post("/api/normalization", json={"session_id": sid}).json()

    # First confirmation
    r1 = client.post(
        "/api/confirmation",
        json={"session_id": sid, "confirmed_text": n["normalized"], "confirmed": True},
    )
    assert r1.status_code == 200
    assert client.post("/api/clinical/extract", json={"session_id": sid}).status_code == 200

    # Second confirmation with updated text
    r2 = client.post(
        "/api/confirmation",
        json={"session_id": sid, "confirmed_text": "আজ মাথায় খুব ব্যথা", "confirmed": True, "edited": True},
    )
    assert r2.status_code == 200
    res2 = r2.json()
    assert res2["confirmed_text"] == "আজ মাথায় খুব ব্যথা"
    assert res2["edited_by_patient"] is True

    # Summary must now be blocked because re-confirmation invalidated downstream states
    assert client.post("/api/summary/generate", json={"session_id": sid}).status_code == 409


def test_extraction_cannot_be_given_text_directly(client):
    sid = demo_session(client)
    r = client.post("/api/clinical/extract", json={"session_id": sid, "text": "বুকে ব্যথা"})
    assert r.status_code == 409  # extra text is ignored; the gate still applies


def test_edit_is_recorded_and_reconfirmation_resets_downstream(client):
    sid = demo_confirmed(client, "A_ordinary")
    assert client.post("/api/clinical/extract", json={"session_id": sid}).status_code == 200
    assert client.post("/api/safety/evaluate", json={"session_id": sid}).status_code == 200
    n = client.post("/api/normalization", json={"session_id": sid}).json()
    c = client.post("/api/confirmation", json={"session_id": sid, "original_text": n["original"],
                                               "confirmed_text": "আজ মাথা ব্যথা", "confirmed": True}).json()
    assert c["edited_by_patient"] is True
    # derived data was invalidated: summary must not be produced from stale extraction
    assert client.post("/api/summary/generate", json={"session_id": sid}).status_code == 409


def test_demo_extraction_refuses_edited_text(client):
    sid = demo_confirmed(client, "A_ordinary", edit="আজ মাথা ব্যথা")
    r = client.post("/api/clinical/extract", json={"session_id": sid})
    assert r.status_code == 409 and r.json()["error"]["code"] == "DEMO_TEXT_EDITED"
