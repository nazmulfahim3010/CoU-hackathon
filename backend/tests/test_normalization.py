import asyncio
import unicodedata

import pytest

from app.config import Settings
from app.services import dialect_normalizer
from app.services.dialect_normalizer import (
    check_meaning_preservation,
    count_negations,
    negation_forms,
    normalize,
)
from app.services.glossary_service import Glossary, clean_text, get_glossary_stats, load_glossary
from conftest import FakeLLM, demo_session


def test_glossary_loads_entries_with_required_fields():
    g = load_glossary()
    assert len(g) == 120
    for entries in g.by_term.values():
        for e in entries:
            for key in (
                "id", "regional_expression", "standard_bangla", "english_meaning", "dialect", "category",
                "example_sentence", "verification_status", "source", "verified_by", "verification_date",
            ):
                assert key in e
            # statuses are copied from the team's CSV: verified rows carry a named verifier
            assert e["verification_status"] == "verified" and e["verified_by"]


def test_glossary_matching_and_substitution():
    g = load_glossary()
    text = "আমার মাথাত বেদনা করের"
    m = g.match(text)
    assert [x.regional for x in m] == ["মাথাত বেদনা"]
    assert Glossary.apply(text, m) == "আমার মাথাব্যথা করের"


def test_glossary_respects_word_boundaries():
    g = load_glossary()
    assert g.match("বেদনার") == []  # 'বেদনা' inside a longer word must not match


def test_longest_match_wins():
    g = load_glossary()
    m = g.match("বুক বেদনা")
    assert [x.regional for x in m] == ["বুক বেদনা"]  # not just "বেদনা"
    assert Glossary.apply("বুক বেদনা", m) == "বুকে ব্যথা"


def test_unicode_normalization_matching():
    g = load_glossary()
    nfd_text = unicodedata.normalize("NFD", "পেটো বেদনা")  # 'ো' decomposes under NFD
    assert nfd_text != unicodedata.normalize("NFC", nfd_text)
    nfc_text = clean_text(nfd_text)
    assert unicodedata.is_normalized("NFC", nfc_text)
    m = g.match(nfd_text)
    assert [x.regional for x in m] == ["পেটো বেদনা"]
    assert Glossary.apply(nfd_text, m) == "পেট ব্যথা"


def test_negation_preserved_by_glossary_only():
    out = asyncio.run(normalize("ওষুধ খাইসিনা", Settings(), use_llm=False))
    forms = negation_forms(load_glossary())
    assert count_negations(out.original, forms) == count_negations(out.normalized, forms) == 1
    assert out.normalized == "ওষুধ খাইনি"
    assert out.source == "glossary_only"
    assert out.glossary_matches and all(m.verification == "verified" for m in out.glossary_matches)


def test_duration_preserved():
    out = asyncio.run(normalize("৩ দিন থাকি আমার জ্বর", Settings(), use_llm=False))
    assert "তিন দিন" in out.normalized


def test_guard_detects_negation_change_and_lost_duration():
    assert "negation_changed" in check_meaning_preservation("জ্বর নাই", "জ্বর আছে")
    assert "number_lost" in check_meaning_preservation("তিন দিন ধরে ব্যথা", "ব্যথা দিন ধরে")
    assert "number_lost" in check_meaning_preservation("৩ দিন ব্যথা", "ব্যথা দিন")
    assert "duration_unit_lost" in check_meaning_preservation("তিন দিন ব্যথা", "তিন ব্যথা")
    assert check_meaning_preservation("৩ দিন থাকি আমার জ্বর", "তিন দিন ধরে আমার জ্বর") == []


def test_guard_detects_invented_symptom():
    g = load_glossary()
    problems = check_meaning_preservation("আমার মাথাত বেদনা করের", "আমার মাথায় ব্যথা সাথে বমি হচ্ছে", g)
    assert "invented_symptom" in problems


def test_llm_output_dropping_negation_is_rejected_after_retry(monkeypatch):
    llm = FakeLLM(['{"normalized": "ওষুধ খেয়েছি", "uncertain_spans": []}', '{"normalized": "ওষুধ খেয়েছি", "uncertain_spans": []}'])
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: llm)
    out = asyncio.run(normalize("ওষুধ খাইসিনা", Settings(), use_llm=True))
    assert out.source == "glossary_only"
    assert out.normalized == "ওষুধ খাইনি"
    assert any("meaning-preservation" in w for w in out.warnings)
    assert llm.calls == 2  # exactly one retry


def test_llm_retry_recovers_from_initial_failure(monkeypatch):
    llm = FakeLLM([
        '{"normalized_text": "ওষুধ খেয়েছি", "changes": [], "uncertain_segments": []}',
        '{"normalized_text": "ওষুধ খাইনি", "changes": [], "uncertain_segments": []}',
    ])
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: llm)
    out = asyncio.run(normalize("ওষুধ খাইসিনা", Settings(), use_llm=True))
    assert out.source == "llm_with_glossary"
    assert out.normalized == "ওষুধ খাইনি"
    assert llm.calls == 2


def test_llm_output_adding_invented_symptom_is_rejected(monkeypatch):
    llm = FakeLLM(['{"normalized_text": "আজ মাথায় ব্যথা ও বুকে ব্যথা আছে", "changes": [], "uncertain_segments": []}'])
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: llm)
    out = asyncio.run(normalize("মাথাত বেদনা", Settings(), use_llm=True))
    assert out.source == "glossary_only"
    assert "বুকে ব্যথা" not in out.normalized
    assert any("meaning-preservation" in w for w in out.warnings)


def test_llm_good_output_accepted_on_sylheti_negation_free_sentence(monkeypatch):
    llm = FakeLLM(['```json\n{"normalized_text": "তিন দিন ধরে আমার মাথায় ব্যথা করছে", "changes": [{"original": "মাথাত বেদনা", "normalized": "মাথায় ব্যথা", "reason": "standard head pain", "source": "glossary"}], "uncertain_segments": [{"text": "বেদনা", "reason": "regional word for pain"}]}\n```'])
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: llm)
    out = asyncio.run(normalize("৩ দিন থাকি আমার মাথাত বেদনা করের", Settings(), use_llm=True))
    assert out.source == "llm_with_glossary" and out.provider == "fake"
    assert "বেদনা" in out.uncertain_spans
    assert out.changes


def test_llm_good_output_with_sylheti_negation_is_accepted(monkeypatch):
    """Regression: dialect negation forms like 'করসিনা' used to cause false rejections."""
    llm = FakeLLM(['{"normalized_text": "আমি এখনো রক্তের পরীক্ষা করিনি", "changes": [], "uncertain_segments": []}'])
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: llm)
    out = asyncio.run(normalize("আমি এখনো রক্তর পরীক্ষা করসিনা", Settings(), use_llm=True))
    assert out.source == "llm_with_glossary"
    assert llm.calls == 1


def test_llm_invalid_json_falls_back(monkeypatch):
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: FakeLLM(["not json at all"]))
    out = asyncio.run(normalize("মাথাত বেদনা", Settings(), use_llm=True))
    assert out.source == "glossary_only" and out.warnings


def test_normalization_route_keeps_original(client):
    sid = demo_session(client, "A_ordinary")
    body = client.post("/api/normalization", json={"session_id": sid}).json()
    assert body["source"] in ("cached_demo_output", "demo_prepared", "llm")
    assert body["original"] != body["normalized"]
    assert "changes" in body
    assert "uncertain_segments" in body


def test_demo_scenarios_exercise_the_sylheti_glossary(client):
    for scenario in ("A_ordinary", "B_red_flag", "C_uncertain"):
        sid = demo_session(client, scenario)
        body = client.post("/api/normalization", json={"session_id": sid}).json()
        assert body["glossary_matches"], scenario


def test_normalization_requires_session(client):
    assert client.post("/api/normalization", json={"session_id": "missing"}).status_code == 404


def test_wrong_session_state_returns_409(client):
    sid = client.post("/api/session", json={"mode": "live"}).json()["session_id"]
    r = client.post("/api/normalization", json={"session_id": sid})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "WORKFLOW_ORDER_VIOLATION"


def test_glossary_stats_endpoint(client):
    r = client.get("/api/glossary/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total_entries"] == 120  # the standard-Bangla reference list is not dialect coverage
    assert data["verified_total"] == 120 and data["unverified_total"] == 0
    assert set(data["by_dialect"]) == {"sylheti", "standard_bangla"}
    assert data["by_dialect"]["sylheti"]["total"] == 120
    assert data["by_dialect"]["sylheti"]["verified"] == 120
    assert data["by_dialect"]["sylheti"]["unverified"] == 0
    assert "text-level review" in data["disclaimer"]


def test_stats_helper_matches_endpoint_logic():
    s = get_glossary_stats()
    assert s.by_dialect["sylheti"].total == 120


def test_script_classification():
    from app.services.transliteration import classify_script

    assert classify_script("আমার মাথা ব্যথা করছে") == "bangla_script"
    assert classify_script("amar mathat bedna korer") == "romanized"
    assert classify_script("amar mathat ব্যথা korer") == "mixed"
    assert classify_script("123 456") == "romanized"
    assert classify_script("১২৩ ৪৫৬") == "bangla_script"


def test_banglish_transliteration_no_invented_symptom():
    """'amar peto bedna korer' gets transliterated and normalized without invented_symptom flag."""
    out = asyncio.run(normalize("amar peto bedna korer", Settings(), use_llm=False))
    assert out.script_type == "romanized"
    assert out.transliterated_text is not None
    assert "পেট" in out.normalized or "পেটে" in out.normalized
    assert "ব্যথা" in out.normalized or "বেদনা" in out.transliterated_text
    assert not any("invented_symptom" in w for w in out.warnings)
    assert any("Roman letters detected" in w for w in out.warnings)


def test_banglish_negation_words_survive_transliteration():
    """Negation words (na, nai, nei, ni, noy) survive transliteration and keep negation intact."""
    from app.services.transliteration import deterministic_transliterate
    from app.services.dialect_normalizer import count_negations, negation_forms

    forms = negation_forms(load_glossary())
    for text in ["mathat betha nai", "amar peto bedna na", "kashi nei", "jor hoy ni"]:
        trans = deterministic_transliterate(text)
        assert count_negations(trans, forms) >= 1
        assert any(neg in trans for neg in ["না", "নাই", "নেই", "নি", "নয়"])


def test_banglish_chest_pain_triggers_red_flag_and_blocks_raw_roman_at_confirmation(client):
    """A Roman chest-pain sentence ('buke betha') triggers CHEST_PAIN after normalization,
    and if submitted directly in Roman script to /api/confirmation it is blocked."""
    from app.services.red_flag_engine import evaluate

    out = asyncio.run(normalize("buke betha", Settings(), use_llm=False))
    assert "বুকে" in out.normalized and "ব্যথা" in out.normalized
    safety = evaluate("test_sess", out.normalized)
    assert any(t.rule_id == "CHEST_PAIN" for t in safety.triggered)

    # Check that confirmation endpoint blocks raw Roman script
    sid = demo_session(client)
    client.post("/api/normalization", json={"session_id": sid})
    r = client.post(
        "/api/confirmation",
        json={"session_id": sid, "confirmed_text": "buke betha", "confirmed": True},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "CONFIRMATION_NON_BANGLA"


def test_banglish_llm_unavailable_falls_back_to_table_with_warning():
    """When LLM is unavailable, transliteration falls back to the deterministic table with a visible warning."""
    out = asyncio.run(normalize("amar peto bedna korer", Settings(), use_llm=False))
    assert out.source == "glossary_only"
    assert any("deterministic table fallback used" in w for w in out.warnings)
    assert any("Roman letters detected" in w for w in out.warnings)
