"""Consent-based sharing of the summary card and voice clip with a health worker (Challenge 1)."""
import pytest

from app.core.exceptions import KothaError
from app.core.share_store import ShareStore, format_code, normalize_code
from conftest import WEBM, demo_confirmed


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def to_summary(client, scenario="B_red_flag"):
    sid = demo_confirmed(client, scenario)
    for path in ("/api/clinical/extract", "/api/safety/evaluate", "/api/summary/generate"):
        assert client.post(path, json={"session_id": sid}).status_code == 200, path
    return sid


def share(client, sid, **form):
    data = {"session_id": sid, "consent": "true", **form}
    return client.post("/api/share", data=data)


# ---------- consent and workflow gates
def test_share_requires_explicit_consent(client):
    sid = to_summary(client)
    assert client.post("/api/share", data={"session_id": sid, "consent": "false"}).status_code == 400
    r = client.post("/api/share", data={"session_id": sid, "consent": "no"})
    assert r.json()["error"]["code"] == "CONSENT_REQUIRED"
    assert client.post("/api/share", data={"session_id": sid}).status_code == 422  # consent missing


def test_share_requires_finished_summary(client):
    sid = demo_confirmed(client, "A_ordinary")  # confirmed but no summary yet
    r = share(client, sid)
    assert r.status_code == 409


def test_share_unknown_session_is_404(client):
    assert share(client, "missing").status_code == 404


# ---------- the health worker gets the SAME card
def test_health_worker_sees_the_same_summary_card(client):
    sid = to_summary(client, "B_red_flag")
    created = share(client, sid)
    assert created.status_code == 201
    body = created.json()
    assert len(body["code"]) == 12 and body["share_path"] == f"/s/{body['code']}"
    assert body["has_audio"] is False
    assert body["display_code"].count("-") == 2

    mine = client.post("/api/summary/generate", json={"session_id": sid}).json()
    theirs = client.get(f"/api/share/{body['code']}")
    assert theirs.status_code == 200
    assert theirs.headers["cache-control"] == "no-store"
    shared = theirs.json()
    assert shared["summary"]["sections"] == mine["sections"]
    assert shared["summary"]["red_flags"] == mine["red_flags"]
    assert {r["rule_id"] for r in shared["summary"]["red_flags"]} == {"CHEST_PAIN", "BREATHING_DIFFICULTY"}
    assert shared["summary"]["original_statement"] == mine["original_statement"]
    assert shared["mode"] == "demo"  # demo shares stay labelled
    assert 0 < shared["seconds_left"] <= 1800


def test_code_is_forgiving_about_case_and_dashes(client):
    sid = to_summary(client)
    body = share(client, sid).json()
    for variant in (body["display_code"], body["code"].lower(), body["display_code"].replace("-", " ").lower()):
        assert client.get(f"/api/share/{variant}").status_code == 200


# ---------- voice clip
def test_audio_is_only_kept_when_the_patient_includes_it(client):
    sid = to_summary(client)
    r = client.post("/api/share", data={"session_id": sid, "consent": "true", "include_audio": "false"},
                    files={"audio": ("clip.webm", WEBM, "audio/webm")})
    body = r.json()
    assert body["has_audio"] is False
    assert client.get(f"/api/share/{body['code']}/audio").status_code == 404  # sent but NOT kept


def test_included_audio_is_served_back(client):
    sid = to_summary(client)
    r = client.post("/api/share", data={"session_id": sid, "consent": "true", "include_audio": "true"},
                    files={"audio": ("clip.webm", WEBM, "audio/webm")})
    assert r.status_code == 201 and r.json()["has_audio"] is True
    code = r.json()["code"]
    a = client.get(f"/api/share/{code}/audio")
    assert a.status_code == 200 and a.content == WEBM and a.headers["content-type"] == "audio/webm"
    assert a.headers["cache-control"] == "no-store"
    assert client.get(f"/api/share/{code}").json()["has_audio"] is True


def test_include_audio_without_a_file_or_with_junk_is_rejected(client):
    sid = to_summary(client)
    r = client.post("/api/share", data={"session_id": sid, "consent": "true", "include_audio": "true"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "AUDIO_REQUIRED"
    r = client.post("/api/share", data={"session_id": sid, "consent": "true", "include_audio": "true"},
                    files={"audio": ("x.webm", b"not audio at all" * 200, "audio/webm")})
    assert r.status_code == 415


# ---------- revoke, expiry, abuse
def test_revoke_deletes_summary_and_audio(client):
    sid = to_summary(client)
    code = client.post("/api/share", data={"session_id": sid, "consent": "true", "include_audio": "true"},
                       files={"audio": ("clip.webm", WEBM, "audio/webm")}).json()["code"]
    assert client.delete(f"/api/share/{code}").status_code == 204
    assert client.get(f"/api/share/{code}").status_code == 404
    assert client.get(f"/api/share/{code}/audio").status_code == 404
    assert client.delete(f"/api/share/{code}").status_code == 204  # idempotent


def test_unknown_code_gives_a_uniform_404(client):
    r = client.get("/api/share/AAAAAAAAAAAA")
    assert r.status_code == 404 and r.json()["error"]["code"] == "SHARE_NOT_FOUND"


def test_store_expiry_removes_summary_and_audio():
    clock = Clock()
    store = ShareStore(60, clock=clock)
    rec = store.create({"x": 1}, "demo", b"AUDIO", "audio/webm")
    assert store.get(rec.code).audio == b"AUDIO"
    clock.t += 61
    with pytest.raises(KothaError) as e:
        store.get(rec.code)
    assert e.value.status_code == 404 and len(store) == 0


def test_purge_expired_drops_everything_in_memory():
    clock = Clock()
    store = ShareStore(60, clock=clock)
    store.create({"a": 1}, "live", b"x" * 10, "audio/webm")
    store.create({"b": 2}, "live")
    clock.t += 120
    assert store.purge_expired() == 2 and len(store) == 0


def test_guessing_is_rate_limited():
    store = ShareStore(60)
    for _ in range(30):
        with pytest.raises(KothaError) as e:
            store.get("NOPENOPENOPE", client="1.2.3.4")
        assert e.value.status_code == 404
    with pytest.raises(KothaError) as e:
        store.get("NOPENOPENOPE", client="1.2.3.4")
    assert e.value.status_code == 429
    store.create({"ok": 1}, "live")  # another client is unaffected
    with pytest.raises(KothaError) as e:
        store.get("NOPENOPENOPE", client="5.6.7.8")
    assert e.value.status_code == 404


def test_codes_are_unguessable_and_unambiguous():
    store = ShareStore(60)
    codes = {store.create({}, "live").code for _ in range(50)}
    assert len(codes) == 50
    for c in codes:
        assert len(c) == 12 and not set(c) & set("01OIL")
    assert normalize_code("abcd-efgh jkmn") == "ABCDEFGHJKMN"
    assert format_code("ABCDEFGHJKMN") == "ABCD-EFGH-JKMN"


def test_capacity_is_bounded():
    store = ShareStore(60)
    for _ in range(100):
        store.create({}, "live")
    with pytest.raises(KothaError) as e:
        store.create({}, "live")
    assert e.value.status_code == 503


def test_share_writes_no_files(client, tmp_path, monkeypatch):
    import os
    monkeypatch.chdir(tmp_path)
    sid = to_summary(client)
    client.post("/api/share", data={"session_id": sid, "consent": "true", "include_audio": "true"},
                files={"audio": ("clip.webm", WEBM, "audio/webm")})
    assert os.listdir(tmp_path) == []


def test_public_base_url_builds_absolute_share_links(settings, client):
    settings.public_base_url = "http://192.168.1.20:8080/"
    sid = to_summary(client)
    body = share(client, sid).json()
    assert body["share_url"] == f"http://192.168.1.20:8080/s/{body['code']}"
