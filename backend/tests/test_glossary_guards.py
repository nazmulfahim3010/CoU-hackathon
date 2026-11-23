"""Glossary-aware meaning-preservation guards, exercised on the verified Sylheti glossary."""
import json

import pytest

from app.services.dialect_normalizer import check_meaning_preservation, negation_forms
from app.services.glossary_service import DATA_DIR, Glossary, load_glossary

ENTRIES = json.loads((DATA_DIR / "dialects" / "sylheti.json").read_text(encoding="utf-8"))["entries"]


def test_sylheti_is_the_only_regional_dialect_loaded():
    dialects = {e.dialect for e in load_glossary().entries}
    assert dialects == {"sylheti"}
    assert len(ENTRIES) == 120


def test_verification_status_is_copied_not_inferred():
    # every row carries the audit trail from the source CSV and nothing is promoted or demoted
    for e in ENTRIES:
        assert e["verification_status"] == "verified"
        assert e["verified_by"] in {"Noyon", "Fahim"}
        assert e["verification_date"]


def test_dialect_negation_forms_are_learned_from_glossary():
    forms = negation_forms(load_glossary())
    assert {"নায়", "করসিনা", "খাইসিনা"} <= forms
    # ordinary words must not be mistaken for negations
    assert "বেদনা" not in forms and "জ্বর" not in forms


@pytest.mark.parametrize("entry", ENTRIES, ids=[e["id"] for e in ENTRIES])
def test_every_verified_example_passes_guards_with_glossary_only_output(entry):
    g = load_glossary()
    sentence = entry["example_sentence"]
    normalized = Glossary.apply(sentence, g.match(sentence))
    assert check_meaning_preservation(sentence, normalized, g) == [], (sentence, normalized)


def test_glossary_phrase_may_turn_a_negated_phrase_into_a_clinical_phrase():
    g = load_glossary()
    assert check_meaning_preservation("হঠাৎ করি আব্বা ঠিক করি মাততে পারে না", "হঠাৎ করি আব্বা কথা জড়িয়ে যাচ্ছে", g) == []


def test_sylheti_negation_forms_are_counted_in_the_original():
    g = load_glossary()
    ok = "আমি এখনো রক্তর পরীক্ষা করিনি"
    assert check_meaning_preservation("আমি এখনো রক্তর পরীক্ষা করসিনা", ok, g) == []
    # LLM turns "haven't done" into "did": must be rejected
    assert "negation_changed" in check_meaning_preservation("আমি এখনো রক্তর পরীক্ষা করসিনা", "আমি এখনো রক্তের পরীক্ষা করেছি", g)


def test_real_negation_drop_is_still_rejected():
    g = load_glossary()
    assert "negation_changed" in check_meaning_preservation("আইজ সকাল থাকি আমার আর জ্বর নাই", "আজ সকাল থেকে আমার জ্বর আছে", g)


def test_unrelated_negation_drop_is_rejected_even_next_to_a_glossary_negation_phrase():
    g = load_glossary()
    original = "আব্বা ঠিক করি মাততে পারে না, জ্বর নাই"
    assert check_meaning_preservation(original, "আব্বা কথা জড়িয়ে যাচ্ছে, জ্বর নেই", g) == []
    assert "negation_changed" in check_meaning_preservation(original, "আব্বা কথা জড়িয়ে যাচ্ছে, জ্বর আছে", g)


def test_invented_symptom_is_still_rejected():
    g = load_glossary()
    original = "আমার মাথাত বেদনা করের"
    assert check_meaning_preservation(original, "আমার মাথায় ব্যথা করছে", g) == []
    assert "invented_symptom" in check_meaning_preservation(original, "আমার মাথায় ব্যথা করছে এবং বুকে ব্যথা", g)
    assert "invented_symptom" in check_meaning_preservation(original, "আমার মাথায় ব্যথা এবং বমি", g)


def test_number_and_duration_are_still_enforced():
    g = load_glossary()
    assert "number_lost" in check_meaning_preservation("৩ দিন থাকি আমার জ্বর", "দিন ধরে আমার জ্বর", g)
    assert "duration_unit_lost" in check_meaning_preservation("তিন দিন ধরি জ্বর", "তিন ধরে জ্বর", g)


def test_a_glossary_time_phrase_may_drop_the_word_for_day():
    # "গত কাইল দিন থাকি" means "since yesterday"; "দিন" here is not a duration
    g = load_glossary()
    assert check_meaning_preservation("গত কাইল দিন থাকি আমার মাথাত বেদনা করের", "গতকাল থেকে আমার মাথায় ব্যথা করছে", g) == []
