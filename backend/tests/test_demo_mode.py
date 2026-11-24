import json
from pathlib import Path
import pytest
from app.config import get_settings
from app.services import text_to_speech
from conftest import demo_confirmed


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
        assert "Synthetic" in s["speaker"]
        assert "not a native" in s["speaker"].lower()  # synthetic voice, never a real speaker


def test_get_demo_audio_stream(client):
    """GET /api/demo/audio/{filename} must serve valid WAV audio."""
    res = client.get("/api/demo/audio/sample_A.wav")
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
    """Live mode must NEVER read cached outputs, failing honestly when LLM key is missing."""
    s = get_settings()
    monkeypatch.setattr(s, "llm_provider", "none")
    monkeypatch.setattr(s, "llm_api_key", "")
    monkeypatch.setattr(s, "llm_model", "")

    # 1. Create a live session
    sess_res = client.post("/api/session", json={"mode": "live"})
    assert sess_res.status_code == 201
    sid = sess_res.json()["session_id"]
    assert sess_res.json()["mode"] == "live"

    # 2. Post a manual typed transcript
    tx_res = client.post(
        "/api/transcription/typed",
        json={"session_id": sid, "text": "আমার বুকে অনেক ব্যথা করছে"},
    )
    assert tx_res.status_code == 200
    assert tx_res.json()["mode"] == "live"
    assert tx_res.json()["source"] == "typed_by_user"

    # 3. Normalize (glossary-only fallback when LLM is unconfigured)
    norm_res = client.post("/api/normalization", json={"session_id": sid})
    assert norm_res.status_code == 200
    assert norm_res.json()["mode"] == "live"
    assert norm_res.json()["source"] == "glossary_only"

    # 4. Confirm
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

    # 5. Extract MUST fail with 503 LLM_UNAVAILABLE and Bangla-friendly error; NEVER read cache
    ext_res = client.post("/api/clinical/extract", json={"session_id": sid})
    assert ext_res.status_code == 503
    err = ext_res.json().get("error", {})
    assert err.get("code") == "LLM_UNAVAILABLE"
    assert "এলএলএম" in err.get("message", "") or "ভাষা মডেল" in err.get("message", "")

    # 6. Verify summary CANNOT be faked/generated
    sum_res = client.post("/api/summary/generate", json={"session_id": sid})
    assert sum_res.status_code == 409  # Gated by state machine


def test_demo_mode_falls_back_to_cached_output_labelled_properly(client, monkeypatch):
    """When LLM is unconfigured, demo mode must use cached_outputs labelled 'cached demo output'."""
    s = get_settings()
    monkeypatch.setattr(s, "llm_provider", "none")
    monkeypatch.setattr(s, "llm_api_key", "")

    sid = client.post("/api/session", json={"mode": "demo", "demo_scenario_id": "A_ordinary"}).json()["session_id"]
    client.post("/api/transcription", data={"session_id": sid, "demo_scenario_id": "A_ordinary"})
    
    norm = client.post("/api/normalization", json={"session_id": sid}).json()
    assert norm["mode"] == "demo"
    assert norm["source"] == "cached_demo_output"
    assert norm["provider"] == "cached_demo_output"
    assert any("cached demo output" in w.lower() for w in norm["warnings"])

    client.post("/api/confirmation", json={"session_id": sid, "original_text": norm["original"], "confirmed_text": norm["normalized"], "confirmed": True})
    ext = client.post("/api/clinical/extract", json={"session_id": sid}).json()
    assert ext["mode"] == "demo"
    assert ext["source"] == "cached_demo_output"
    assert ext["provider"] == "cached_demo_output"
    assert "cached demo output" in ext["note"].lower()


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


def test_demo_responses_never_label_sample_or_cached_as_verified_without_native_verification(client):
    """Guardrail test: Demo and cached responses must NEVER be labelled as 'verified'
    unless accompanied by a legitimate team native-speaker verification."""
    import re

    # 1. Samples check
    samples_res = client.get("/api/demo/samples")
    assert samples_res.status_code == 200
    samples = samples_res.json()
    assert len(samples) > 0

    for s in samples:
        # Must have a non-empty verified_by field
        assert "verified_by" in s
        assert bool(s["verified_by"].strip())
        # If not native-speaker verified, cannot claim verified in title/purpose
        assert not re.search(r"\bverified\b", s["title"], re.IGNORECASE)
        assert "যাচাইকৃত" not in s["title"]
        assert not re.search(r"\bverified\b", s["purpose"], re.IGNORECASE)

    # 2. Pipeline output checks (fallback / cached demo mode)
    for scenario_id in ("A_ordinary", "B_red_flag", "C_uncertain"):
        sid = client.post("/api/session", json={"mode": "demo", "demo_scenario_id": scenario_id}).json()["session_id"]
        
        # Transcription response
        tx = client.post("/api/transcription", data={"session_id": sid, "demo_scenario_id": scenario_id}).json()
        assert not re.search(r"\bverified\b", tx.get("disclaimer", ""), re.IGNORECASE)
        assert "যাচাইকৃত" not in tx.get("disclaimer", "")

        # Normalization response (fallback)
        norm = client.post("/api/normalization", json={"session_id": sid}).json()
        for w in norm.get("warnings", []):
            assert "pre-verified" not in w.lower()
            assert not re.search(r"\bverified\b", w, re.IGNORECASE)
            assert "যাচাইকৃত" not in w

        # Confirmation
        client.post("/api/confirmation", json={
            "session_id": sid,
            "original_text": norm["original"],
            "confirmed_text": norm["normalized"],
            "confirmed": True
        })

        # Extraction response (fallback)
        ext = client.post("/api/clinical/extract", json={"session_id": sid}).json()
        note = ext.get("note", "")
        assert "pre-verified" not in note.lower()
        assert not re.search(r"\bverified\b", note, re.IGNORECASE)
        assert "যাচাইকৃত" not in note


def test_raw_datasets_source_md_exists_and_contains_table():
    """Assert demo_assets/raw_datasets/SOURCE.md exists and contains a valid markdown table."""
    source_md = Path(__file__).resolve().parents[2] / "demo_assets" / "raw_datasets" / "SOURCE.md"
    assert source_md.exists(), "demo_assets/raw_datasets/SOURCE.md must exist"

    content = source_md.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines()]

    # Check for markdown table indicators (header separator like |---|---|)
    table_separator = [line for line in lines if line.startswith("|") and "---" in line]
    assert len(table_separator) >= 1, "SOURCE.md must contain a markdown table with separator '|---|'"

    # Verify required headers and listed dataset files
    assert "| filename" in content.lower() or "| file" in content.lower()
    for fname in [
        "Barishal_NER.csv",
        "Chittagong_NER.csv",
        "Mymensingh_NER.csv",
        "Noakhali_NER.csv",
        "Regional_NER (Raw Sentences).csv",
        "Sylhet_NER.csv",
    ]:
        assert fname in content, f"{fname} must be documented in SOURCE.md"


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

