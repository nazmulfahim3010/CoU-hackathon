"""Challenge 2: Kotha must never turn a dialect phrase into a symptom the patient never described.

Covers the deterministic grounding layer (every claim needs a verbatim quote from the patient's confirmed
words), the retry/removal behaviour of the extractor, and the normalization step itself.
"""
import asyncio
import json

import pytest

from app.config import Settings
from app.schemas.clinical import BilingualField, ClinicalExtraction, Item
from app.services import clinical_extractor
from app.services.glossary_service import DATA_DIR, Glossary, load_glossary
from app.services.grounding import evidence_is_verbatim, ground_extraction, squash, symptoms_named_but_never_said
from conftest import FakeLLM, demo_confirmed

NR = BilingualField(status="not_reported")


def ext(**over) -> ClinicalExtraction:
    base = dict(chief_complaint=NR, duration=NR, severity=NR, relevant_history=NR, current_medications=NR, allergies=NR)
    base.update(over)
    return ClinicalExtraction(**base)


def item(bn, en, ev):
    return Item(bn=bn, en=en, evidence=ev)


CONFIRMED = "আমার মাথাত বেদনা করের"  # patient said: headache (dialect). NOT chest pain.


# ---------- the core guarantee
def test_invented_symptom_with_a_fabricated_quote_is_removed():
    e = ext(symptoms=[item("মাথাব্যথা", "Headache", "মাথাত বেদনা"), item("বুকে ব্যথা", "Chest pain", "বুকে ব্যথা")])
    out = ground_extraction(e, CONFIRMED)
    assert [i.en for i in out.symptoms] == ["Headache"]
    assert [i.en for i in out.removed_ungrounded] == ["Chest pain"]  # recorded, not silently dropped


def test_invented_symptom_hiding_behind_a_real_quote_of_another_symptom_is_removed():
    # the quote is real, but it does not support a chest-pain claim
    e = ext(symptoms=[item("বুকে ব্যথা", "Chest pain", "মাথাত বেদনা")])
    out = ground_extraction(e, CONFIRMED)
    assert out.symptoms == [] and [i.en for i in out.removed_ungrounded] == ["Chest pain"]


def test_symptom_with_no_evidence_at_all_is_removed():
    out = ground_extraction(ext(symptoms=[item("মাথাব্যথা", "Headache", None)]), CONFIRMED)
    assert out.symptoms == [] and len(out.removed_ungrounded) == 1


def test_grounded_symptoms_are_kept_with_their_quote():
    out = ground_extraction(ext(symptoms=[item("মাথাব্যথা", "Headache", "মাথাত বেদনা")]), CONFIRMED)
    assert out.symptoms[0].evidence == "মাথাত বেদনা" and out.removed_ungrounded == []


def test_dialect_and_standard_variants_of_the_same_symptom_both_count():
    # patient confirmed standard "মাথায় ব্যথা"; model writes the compound form "মাথাব্যথা" quoting the patient's words
    out = ground_extraction(ext(symptoms=[item("মাথাব্যথা", "Headache", "মাথায় ব্যথা")]), "আমার মাথায় ব্যথা করছে")
    assert len(out.symptoms) == 1 and out.removed_ungrounded == []


def test_chief_complaint_naming_a_symptom_never_said_is_cleared():
    e = ext(chief_complaint=BilingualField(status="reported", bn="বুকে ব্যথা", en="Chest pain", evidence="বুকে ব্যথা"))
    out = ground_extraction(e, CONFIRMED)
    assert out.chief_complaint.status == "not_reported" and out.chief_complaint.bn is None
    assert out.removed_ungrounded and out.removed_ungrounded[0].en == "Chest pain"


def test_field_without_a_real_quote_is_demoted_to_uncertain_not_reported_as_fact():
    e = ext(duration=BilingualField(status="reported", bn="তিন দিন", en="Three days", evidence="তিন দিন ধরে"))
    out = ground_extraction(e, CONFIRMED)  # the patient never gave a duration
    assert out.duration.status == "uncertain" and out.duration.bn == "তিন দিন"
    assert any("could not be matched" in i.en for i in out.uncertain_or_missing)


def test_negative_symptoms_must_also_be_grounded():
    e = ext(negative_symptoms=[item("বমি নেই", "No vomiting", "বমি নেই")])
    out = ground_extraction(e, CONFIRMED)  # patient never said anything about vomiting: not a "negative finding"
    assert out.negative_symptoms == [] and len(out.removed_ungrounded) == 1


def test_grounding_is_idempotent():
    e = ext(symptoms=[item("বুকে ব্যথা", "Chest pain", "বুকে ব্যথা"), item("মাথাব্যথা", "Headache", "মাথাত বেদনা")])
    once = ground_extraction(e, CONFIRMED)
    assert ground_extraction(once, CONFIRMED) == once


def test_evidence_matching_ignores_punctuation_and_spacing_only():
    sq = squash("আজ সকাল থেকে, আমার জ্বর আছে।")
    assert evidence_is_verbatim("আমার জ্বর আছে", sq)
    assert evidence_is_verbatim("সকাল থেকে আমার জ্বর", sq)
    assert not evidence_is_verbatim("আমার বুকে ব্যথা", sq)
    assert not evidence_is_verbatim("", sq) and not evidence_is_verbatim(None, sq)


# ---------- extractor: corrective retry, then removal (never keep)
def llm_json(symptoms, **extra):
    d = {"chief_complaint": {"status": "not_reported"}, "symptoms": symptoms,
         "duration": {"status": "not_reported"}, "severity": {"status": "not_reported"},
         "relevant_history": {"status": "not_reported"}, "current_medications": {"status": "not_reported"},
         "allergies": {"status": "not_reported"}, "associated_symptoms": [], "negative_symptoms": [],
         "uncertain_or_missing": [], "model_noted_red_flag_indicators": []}
    d.update(extra)
    return json.dumps(d, ensure_ascii=False)


BAD = [{"bn": "মাথাব্যথা", "en": "Headache", "evidence": "মাথাত বেদনা"},
       {"bn": "বুকে ব্যথা", "en": "Chest pain", "evidence": "বুকে ব্যথা"}]
GOOD = [{"bn": "মাথাব্যথা", "en": "Headache", "evidence": "মাথাত বেদনা"}]


def test_extractor_retries_with_feedback_and_accepts_the_corrected_answer(monkeypatch):
    llm = FakeLLM([llm_json(BAD), llm_json(GOOD)])
    monkeypatch.setattr(clinical_extractor, "get_llm", lambda s: llm)
    out = asyncio.run(clinical_extractor.extract(CONFIRMED, Settings()))
    assert llm.calls == 2
    assert [i.en for i in out.symptoms] == ["Headache"] and out.removed_ungrounded == []


def test_extractor_never_keeps_an_invented_symptom_even_if_the_model_insists(monkeypatch):
    llm = FakeLLM([llm_json(BAD)])  # repeats the same bad answer on every attempt
    monkeypatch.setattr(clinical_extractor, "get_llm", lambda s: llm)
    out = asyncio.run(clinical_extractor.extract(CONFIRMED, Settings()))
    assert llm.calls == clinical_extractor.MAX_ATTEMPTS
    assert [i.en for i in out.symptoms] == ["Headache"]
    assert [i.en for i in out.removed_ungrounded] == ["Chest pain"]  # surfaced to the clinician


def test_prompt_demands_verbatim_evidence_and_forbids_unsaid_symptoms():
    assert '"evidence"' in clinical_extractor.SYSTEM and "EXACT substring" in clinical_extractor.SYSTEM
    assert "did not say" in clinical_extractor.SYSTEM or "not say" in clinical_extractor.SYSTEM


# ---------- demo path and summary: the clinician sees real quotes
@pytest.mark.parametrize("scenario", ["A_ordinary", "B_red_flag", "C_uncertain"])
def test_prepared_demo_extractions_are_fully_grounded(client, scenario):
    sid = demo_confirmed(client, scenario)
    body = client.post("/api/clinical/extract", json={"session_id": sid}).json()["extraction"]
    assert body["removed_ungrounded"] == []
    for name in ("chief_complaint", "duration"):
        if body[name]["status"] == "reported":
            assert body[name]["evidence"], name  # a real quote, not the model's own words
    for it in body["symptoms"]:
        assert it["evidence"]


def test_summary_shows_the_patients_own_words_as_evidence(client):
    sid = demo_confirmed(client, "B_red_flag")
    for path in ("/api/clinical/extract", "/api/safety/evaluate"):
        client.post(path, json={"session_id": sid})
    card = client.post("/api/summary/generate", json={"session_id": sid}).json()
    sec = {s["key"]: s for s in card["sections"]}
    assert sec["chief_complaint"]["evidence"] == "বুকে ব্যথা"
    assert "বুকে ব্যথা" in (sec["symptoms"]["evidence"] or "")
    assert card["removed_ungrounded"] == []


# ---------- the normalization step itself
EXAMPLES = [e for e in json.loads((DATA_DIR / "dialects" / "sylheti.json").read_text(encoding="utf-8"))["entries"]]


@pytest.mark.parametrize("entry", EXAMPLES, ids=[e["id"] for e in EXAMPLES])
def test_glossary_normalization_never_introduces_a_symptom_the_original_lacks(entry):
    g = load_glossary()
    original = entry["example_sentence"]
    normalized = Glossary.apply(original, g.match(original))
    assert symptoms_named_but_never_said(normalized, squash(original)) == [], (original, normalized)


def test_the_check_would_catch_a_real_invention():
    original = "আমার মাথাত বেদনা করের"
    assert symptoms_named_but_never_said("আমার মাথায় ব্যথা এবং বুকে ব্যথা", squash(original)) == ["chest_pain"]
    assert symptoms_named_but_never_said("আমার মাথায় ব্যথা এবং বমি", squash(original)) == ["vomiting"]
