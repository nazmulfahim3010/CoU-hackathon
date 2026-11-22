import base64
import pytest
from app.schemas.clinical import Item
from app.services import text_to_speech
from app.services.text_to_speech import build_spoken_template_text


def test_spoken_template_without_red_flags():
    text = build_spoken_template_text(has_urgent_or_emergency=False)
    assert "আপনার তথ্য ডাক্তারের কাছে পাঠানোর জন্য লেখা হয়েছে।" in text
    assert "ডাক্তারই আপনার চিকিৎসার সিদ্ধান্ত নেবেন।" in text
    assert "জরুরি" not in text
    # Verify no diagnostic claims are made
    for phrase in ("রোগ নির্ণয় করা হয়েছে", "আপনার রোগ হয়েছে", "প্রেসক্রিপশন", "ওষুধ খান"):
        assert phrase not in text


def test_spoken_template_with_urgent_flag_includes_calm_instruction():
    text = build_spoken_template_text(has_urgent_or_emergency=True)
    assert "আপনার কথায় জরুরি কিছু লক্ষণ দেখা গেছে।" in text
    assert "নিকটস্থ স্বাস্থ্য কমপ্লেক্স বা হাসপাতালে যোগাযোগ করুন" in text
    assert "ডাক্তারই আপনার চিকিৎসার সিদ্ধান্ত নেবেন।" in text


def test_spoken_template_includes_missing_questions():
    missing = [Item(bn="কবে থেকে শুরু হয়েছে", en="Onset"), Item(bn="কতটা তীব্র", en="Severity")]
    text = build_spoken_template_text(has_urgent_or_emergency=False, uncertain_or_missing=missing)
    assert "ডাক্তার হয়তো আপনার কাছে জানতে চাইতে পারেন:" in text
    assert "কবে থেকে শুরু হয়েছে" in text
    assert "কতটা তীব্র" in text


def test_summary_and_speech_end_to_end_and_state_gates(client):
    from conftest import demo_session, demo_confirmed

    # 1. State gates: cannot call summary before EVALUATED
    sid = demo_confirmed(client, "A_ordinary")
    assert client.post("/api/summary/generate", json={"session_id": sid}).status_code == 409

    # Advance to EXTRACTED
    client.post("/api/clinical/extract", json={"session_id": sid})
    assert client.post("/api/summary/generate", json={"session_id": sid}).status_code == 409

    # Advance to EVALUATED
    client.post("/api/safety/evaluate", json={"session_id": sid})

    # Now generate summary -> Should succeed with 200
    sum_res = client.post("/api/summary/generate", json={"session_id": sid})
    assert sum_res.status_code == 200
    card = sum_res.json()

    # Check all required sections
    keys = {s["key"] for s in card["sections"]}
    expected_keys = {
        "chief_complaint", "symptoms", "duration", "severity",
        "history", "medications", "allergies", "associated",
        "negatives", "uncertain", "model_noted"
    }
    assert expected_keys.issubset(keys)

    # Check required metadata
    assert card["original_statement"]
    assert card["normalized_statement"]
    assert card["confirmed_statement"]
    assert card["label_en"] == "AI-assisted patient intake summary — clinician verification required."
    assert "not a diagnostic tool" in card["disclaimer_en"].lower()
    assert "কোনো রোগ নির্ণয়ের সরঞ্জাম নয়" in card["disclaimer_bn"]

    # 2. State gate for speech: requires SUMMARIZED
    sid_unsummarized = demo_confirmed(client, "B_red_flag")
    assert client.post("/api/speech/generate", json={"session_id": sid_unsummarized}).status_code == 409

    # 3. Speech generation for ordinary scenario
    speech_res = client.post("/api/speech/generate", json={"session_id": sid})
    assert speech_res.status_code == 200
    speech_data = speech_res.json()
    assert speech_data["session_id"] == sid
    assert speech_data["provider"] == "gtts"
    assert speech_data["mime_type"] == "audio/mpeg"
    assert "জরুরি" not in speech_data["text_bn"]

    # Decode audio to verify valid MP3 header bytes
    audio_bytes = base64.b64decode(speech_data["audio_base64"])
    assert len(audio_bytes) > 1000
    assert audio_bytes[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"ID") or b"LAME" in audio_bytes[:100]

    # Verify speech text endpoint
    text_res = client.get(f"/api/speech/text/{sid}")
    assert text_res.status_code == 200
    assert text_res.json()["text_bn"] == speech_data["text_bn"]


def test_speech_generation_with_emergency_rule(client):
    from conftest import demo_confirmed
    sid = demo_confirmed(client, "B_red_flag")
    client.post("/api/clinical/extract", json={"session_id": sid})
    client.post("/api/safety/evaluate", json={"session_id": sid})
    client.post("/api/summary/generate", json={"session_id": sid})

    speech_res = client.post("/api/speech/generate", json={"session_id": sid})
    assert speech_res.status_code == 200
    speech_data = speech_res.json()
    assert "জরুরি" in speech_data["text_bn"]
    assert "নিকটস্থ স্বাস্থ্য কমপ্লেক্স বা হাসপাতালে যোগাযোগ করুন" in speech_data["text_bn"]
