import json
from pathlib import Path
import pytest
from app.config import get_settings


def test_list_demo_samples(client):
    """GET /api/demo/samples must list all 3 prepared scenarios with audio URLs."""
    res = client.get("/api/demo/samples")
    assert res.status_code == 200
    samples = res.json()
    assert len(samples) >= 3

    ids = {s["id"] for s in samples}
    assert {"A_ordinary", "B_red_flag", "C_uncertain"}.issubset(ids)

    for s in samples:
        assert s["audio_file"].endswith(".wav")
        assert s["audio_url"].startswith("/api/demo/audio/")
        assert len(s["original_transcript"]) > 0
        assert len(s["standard_bangla"]) > 0
        assert s["speaker"]


def test_get_demo_audio_stream(client):
    """GET /api/demo/audio/{filename} must serve valid WAV audio."""
    res = client.get("/api/demo/audio/sample_sylheti_01.wav")
    assert res.status_code == 200
    assert "audio" in res.headers.get("content-type", "")
    assert res.content[:4] == b"RIFF"
    assert res.content[8:12] == b"WAVE"

    # Non-existent file gives 404
    assert client.get("/api/demo/audio/non_existent.wav").status_code == 404


def test_demo_live_asr_comparison(client):
    """POST /api/demo/live-asr runs live ASR on a demo sample for judge comparison."""
    res = client.post("/api/demo/live-asr", json={"sample_id": "A_ordinary"})
    assert res.status_code == 200
    data = res.json()
    assert data["sample_id"] == "A_ordinary"
    assert data["source"] == "speech_recognition"
    assert data["mode"] == "live"
    assert "provider" in data
    assert len(data["transcript"]) > 0


def test_demo_responses_carry_mode_demo_at_every_step(client):
    """All API responses in demo mode must carry mode: 'demo'."""
    # 1. Create demo session
    sess_res = client.post("/api/session", json={"mode": "demo", "demo_scenario_id": "A_ordinary"})
    assert sess_res.status_code == 201
    sess_data = sess_res.json()
    assert sess_data["mode"] == "demo"
    sid = sess_data["session_id"]

    # 2. Transcription
    tx_res = client.post("/api/transcription", data={"session_id": sid, "demo_scenario_id": "A_ordinary"})
    assert tx_res.status_code == 200
    tx_data = tx_res.json()
    assert tx_data["mode"] == "demo"
    assert tx_data["source"] == "demo_sample"

    # 3. Normalization
    norm_res = client.post("/api/normalization", json={"session_id": sid})
    assert norm_res.status_code == 200
    norm_data = norm_res.json()
    assert norm_data["mode"] == "demo"

    # 4. Confirmation
    conf_res = client.post(
        "/api/confirmation",
        json={
            "session_id": sid,
            "original_text": norm_data["original"],
            "confirmed_text": norm_data["normalized"],
            "confirmed": True,
        },
    )
    assert conf_res.status_code == 200
    conf_data = conf_res.json()
    assert conf_data["mode"] == "demo"

    # 5. Extraction
    ext_res = client.post("/api/clinical/extract", json={"session_id": sid})
    assert ext_res.status_code == 200
    ext_data = ext_res.json()
    assert ext_data["mode"] == "demo"

    # 6. Safety evaluation
    safe_res = client.post("/api/safety/evaluate", json={"session_id": sid})
    assert safe_res.status_code == 200
    safe_data = safe_res.json()
    assert safe_data["mode"] == "demo"

    # 7. Summary generation
    sum_res = client.post("/api/summary/generate", json={"session_id": sid})
    assert sum_res.status_code == 200
    sum_data = sum_res.json()
    assert sum_data["mode"] == "demo"

    # 8. Speech generation
    sp_res = client.post("/api/speech/generate", json={"session_id": sid})
    assert sp_res.status_code == 200
    sp_data = sp_res.json()
    assert sp_data["mode"] == "demo"


def test_live_mode_never_reads_cached_outputs(client, monkeypatch):
    """Live mode must NEVER read cached outputs, failing properly when unconfigured."""
    # Create a live session
    sess_res = client.post("/api/session", json={"mode": "live"})
    sid = sess_res.json()["session_id"]

    # Post a manual typed transcript
    tx_res = client.post(
        "/api/transcription/typed",
        json={"session_id": sid, "text": "আমার বুকে অনেক ব্যথা করছে"},
    )
    assert tx_res.status_code == 200
    assert tx_res.json()["mode"] == "live"

    # Normalize
    norm_res = client.post("/api/normalization", json={"session_id": sid})
    assert norm_res.status_code == 200
    assert norm_res.json()["mode"] == "live"

    # Confirm
    conf_res = client.post(
        "/api/confirmation",
        json={
            "session_id": sid,
            "original_text": "আমার বুকে অনেক ব্যথা করছে",
            "confirmed_text": "আমার বুকে অনেক ব্যথা করছে",
            "confirmed": True,
        },
    )
    assert conf_res.status_code == 200
    assert conf_res.json()["mode"] == "live"

    # In live mode with no LLM configured, extract must raise 503 / ProviderNotConfigured, NOT read cache
    s = get_settings()
    monkeypatch.setattr(s, "llm_provider", "unconfigured")
    ext_res = client.post("/api/clinical/extract", json={"session_id": sid})
    assert ext_res.status_code in (500, 502, 503)
    assert ext_res.json().get("error", {}).get("code") != "CACHE_LOADED"


def test_scenario_b_triggers_red_flag_rules(client):
    """Scenario B represents chest pain with breathlessness; safety rules must trigger."""
    # Run pipeline up to safety evaluation
    sid = client.post("/api/session", json={"mode": "demo", "demo_scenario_id": "B_red_flag"}).json()["session_id"]
    tx = client.post("/api/transcription", data={"session_id": sid, "demo_scenario_id": "B_red_flag"}).json()
    norm = client.post("/api/normalization", json={"session_id": sid}).json()
    client.post(
        "/api/confirmation",
        json={"session_id": sid, "original_text": norm["original"], "confirmed_text": norm["normalized"], "confirmed": True},
    )
    client.post("/api/clinical/extract", json={"session_id": sid})

    safe = client.post("/api/safety/evaluate", json={"session_id": sid}).json()
    triggered_ids = {r["rule_id"] for r in safe["triggered"]}

    assert "CHEST_PAIN" in triggered_ids
    assert "BREATHING_DIFFICULTY" in triggered_ids

    # Summary must contain red-flag warnings
    summary = client.post("/api/summary/generate", json={"session_id": sid}).json()
    flag_ids = {r["rule_id"] for r in summary["red_flags"]}
    assert "CHEST_PAIN" in flag_ids
    assert "BREATHING_DIFFICULTY" in flag_ids


def test_scenario_c_produces_uncertain_items(client):
    """Scenario C has hedged/incomplete info; uncertain_or_missing items must be preserved."""
    sid = client.post("/api/session", json={"mode": "demo", "demo_scenario_id": "C_uncertain"}).json()["session_id"]
    client.post("/api/transcription", data={"session_id": sid, "demo_scenario_id": "C_uncertain"})
    norm = client.post("/api/normalization", json={"session_id": sid}).json()
    client.post(
        "/api/confirmation",
        json={"session_id": sid, "original_text": norm["original"], "confirmed_text": norm["normalized"], "confirmed": True},
    )
    client.post("/api/clinical/extract", json={"session_id": sid})
    client.post("/api/safety/evaluate", json={"session_id": sid})
    summary = client.post("/api/summary/generate", json={"session_id": sid}).json()

    # Look for uncertain section
    uncertain_sec = next((s for s in summary["sections"] if s["key"] == "uncertain"), None)
    assert uncertain_sec is not None
    assert len(uncertain_sec["en"]) > 0 or len(uncertain_sec["bn"]) > 0
    # Must contain note about duration or fever uncertainty
    text_blob = " ".join(uncertain_sec["en"] + uncertain_sec["bn"]).lower()
    assert any(term in text_blob for term in ("duration", "fever", "সময়", "জ্বর", "ঔষধ", "medication"))


def test_full_demo_flow_all_three_scenarios(client):
    """All 3 scenarios must execute the entire 8-step pipeline without errors."""
    for scenario_id in ("A_ordinary", "B_red_flag", "C_uncertain"):
        # 1. Session
        sid = client.post("/api/session", json={"mode": "demo", "demo_scenario_id": scenario_id}).json()["session_id"]

        # 2. Transcription
        tx = client.post("/api/transcription", data={"session_id": sid, "demo_scenario_id": scenario_id})
        assert tx.status_code == 200

        # 3. Normalization
        norm = client.post("/api/normalization", json={"session_id": sid})
        assert norm.status_code == 200
        norm_data = norm.json()

        # 4. Confirmation
        conf = client.post(
            "/api/confirmation",
            json={
                "session_id": sid,
                "original_text": norm_data["original"],
                "confirmed_text": norm_data["normalized"],
                "confirmed": True,
            },
        )
        assert conf.status_code == 200

        # 5. Extraction
        ext = client.post("/api/clinical/extract", json={"session_id": sid})
        assert ext.status_code == 200

        # 6. Safety check
        safe = client.post("/api/safety/evaluate", json={"session_id": sid})
        assert safe.status_code == 200

        # 7. Summary
        summ = client.post("/api/summary/generate", json={"session_id": sid})
        assert summ.status_code == 200

        # 8. Spoken reply
        sp = client.post("/api/speech/generate", json={"session_id": sid})
        assert sp.status_code == 200
        sp_data = sp.json()
        assert len(sp_data["audio_base64"]) > 0
        assert len(sp_data["text_bn"]) > 0
