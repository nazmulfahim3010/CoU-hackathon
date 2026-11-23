"""Deterministic red-flag coverage for verified Sylheti phrasings.

Both inputs a clinician could see are tested: the raw Sylheti sentence (e.g. if the patient confirms
unnormalized text) and the glossary-normalized standard Bangla. No LLM is involved anywhere.
"""
import json

import pytest

from app.services.glossary_service import DATA_DIR, Glossary, load_glossary
from app.services.red_flag_engine import evaluate

EXAMPLES = {
    e["id"]: e["example_sentence"]
    for e in json.loads((DATA_DIR / "dialects" / "sylheti.json").read_text(encoding="utf-8"))["entries"]
}

# verified example id -> rule that must trigger
MUST_TRIGGER = {
    "syl_009": "CHEST_PAIN",
    "syl_010": "CHEST_PAIN",
    "syl_013": "CHEST_PAIN",
    "syl_018": "BREATHING_DIFFICULTY",
    "syl_099": "BREATHING_DIFFICULTY",
    "syl_019": "HEAVY_BLEEDING",
    "syl_020": "UNCONSCIOUSNESS",
    "syl_021": "SEIZURE",
    "syl_022": "BLOOD_IN_VOMIT_STOOL",
    "syl_023": "STROKE_SIGNS",
    "syl_024": "STROKE_SIGNS",
    "syl_025": "STROKE_SIGNS",
}


def _normalized(sentence: str) -> str:
    g = load_glossary()
    return Glossary.apply(sentence, g.match(sentence))


def _triggered(confirmed: str, original: str | None = None) -> set[str]:
    return {r.rule_id for r in evaluate("t", confirmed, original_transcript=original).triggered}


@pytest.mark.parametrize("sid,rule", sorted(MUST_TRIGGER.items()))
def test_raw_sylheti_triggers(sid, rule):
    s = EXAMPLES[sid]
    assert rule in _triggered(s), (sid, s)


@pytest.mark.parametrize("sid,rule", sorted(MUST_TRIGGER.items()))
def test_glossary_normalized_text_triggers(sid, rule):
    s = EXAMPLES[sid]
    n = _normalized(s)
    assert rule in _triggered(n), (sid, n)
    assert rule in _triggered(n, original=s)


def test_hyphenated_limb_weakness_is_caught():
    # glossary maps "হাত পা সলের না" to "হাত-পা অবশ হয়ে গেছে": the hyphen must not hide it
    assert "STROKE_SIGNS" in _triggered("বাম সাইডর হাত-পা অবশ হয়ে গেছে")


def test_sylheti_negation_suppresses_alert_but_is_reported():
    r = evaluate("t", "বুক বেদনা নায়, মাথাত বেদনা করের")
    assert r.triggered == []
    assert [x.rule_id for x in r.explicitly_denied] == ["CHEST_PAIN"]


def test_unrelated_sylheti_negation_does_not_hide_chest_pain():
    assert "CHEST_PAIN" in _triggered("বুক বেদনা করের, খাইতে পাররাম না")


def test_infant_fever_in_sylheti_needs_information_without_age():
    r = evaluate("t", EXAMPLES["syl_043"])  # "বাইচাটার খুব বেশি জ্বর"
    assert r.triggered == []
    assert [x.rule_id for x in r.insufficient_information] == ["INFANT_FEVER"]


def test_infant_fever_triggers_when_age_in_months_is_stated():
    assert "INFANT_FEVER" in _triggered("আমার বাইচাটার আট মাস বয়স, দুই দিন ধরি জ্বর")


def test_infant_fever_triggers_from_intake_age_group():
    r = evaluate("t", "বাইচাটার জ্বর", age_group="infant")
    assert [x.rule_id for x in r.triggered] == ["INFANT_FEVER"]


# Ordinary complaints in the verified set must NOT raise emergency alerts.
ORDINARY = ["syl_027", "syl_028", "syl_029", "syl_031", "syl_032", "syl_033", "syl_044", "syl_045", "syl_095"]


@pytest.mark.parametrize("sid", ORDINARY)
def test_ordinary_symptoms_do_not_trigger(sid):
    s = EXAMPLES[sid]
    assert _triggered(s) == set(), (sid, s)
    assert _triggered(_normalized(s), original=s) == set(), sid


def test_nosebleed_alone_is_not_an_emergency_alert():
    # deliberate: "রক্ত বারর" alone is generic bleeding; only continuous bleeding ("অনবরত রক্ত") alerts
    assert _triggered(EXAMPLES["syl_098"]) == set()


def test_no_alert_never_claims_safety():
    r = evaluate("t", "মাথাত বেদনা করের")
    assert r.triggered == []
    assert "does not mean the patient is safe" in r.notice_en
