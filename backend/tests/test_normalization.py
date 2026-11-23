import asyncio
import unicodedata
import pytest

from app.config import Settings
from app.services import dialect_normalizer
from app.services.dialect_normalizer import check_meaning_preservation, count_negations, normalize
from app.services.glossary_service import Glossary, clean_text, get_glossary_stats, load_glossary
from conftest import FakeLLM, demo_session


def test_glossary_loads_entries_with_required_fields():
    g = load_glossary()
    assert len(g) >= 20
    for entries in g.by_term.values():
        for e in entries:
            for key in ("id", "regional_expression", "standard_bangla", "english_meaning", "dialect", "category", "example_sentence", "verification_status", "source"):
                assert key in e
            assert e["verification_status"] == "unverified"  # nothing in regional dialects is claimed as verified


def test_glossary_matching_and_substitution():
    g = load_glossary()
    text = "মোর মাতাত ব্যতা"
    m = g.match(text)
    assert [x.regional for x in m] == ["মাতাত", "ব্যতা"]
    assert Glossary.apply(text, m) == "মোর মাথায় ব্যথা"


def test_glossary_respects_word_boundaries():
    g = load_glossary()
    assert g.match("আইজকাল") == []  # 'আইজ' inside a longer word must not match


def test_longest_match_wins():
    g = load_glossary()
    m = g.match("বুঝি নাই")
    assert [x.regional for x in m] == ["বুঝি নাই"]
    assert Glossary.apply("বুঝি নাই", m) == "বুঝিনি"


def test_unicode_normalization_matching():
    g = load_glossary()
    # NFD decomposed string
    nfd_text = unicodedata.normalize("NFD", "মোর মাতাত ব্যতা")
    # clean_text normalizes to NFC
    nfc_text = clean_text(nfd_text)
    assert unicodedata.is_normalized("NFC", nfc_text)
    m = g.match(nfd_text)
    assert [x.regional for x in m] == ["মাতাত", "ব্যতা"]
    assert Glossary.apply(nfd_text, m) == "মোর মাথায় ব্যথা"


def test_negation_preserved_by_glossary_only():
    out = asyncio.run(normalize("ওষুধ খাই নাই", Settings(), use_llm=False))
    assert count_negations(out.original) == count_negations(out.normalized) == 1
    assert out.source == "glossary_only"
    assert any("unverified" in m.verification for m in out.glossary_matches)


def test_duration_preserved():
    out = asyncio.run(normalize("আইজ তিন দিন ধরি ব্যতা", Settings(), use_llm=False))
    assert "তিন দিন" in out.normalized


def test_guard_detects_negation_change_and_lost_duration():
    assert "negation_changed" in check_meaning_preservation("জ্বর নাই", "জ্বর আছে")
    assert "number_lost" in check_meaning_preservation("তিন দিন ধরে ব্যথা", "ব্যথা দিন ধরে")
    assert "number_lost" in check_meaning_preservation("৩ দিন ব্যথা", "ব্যথা দিন")
    assert "duration_unit_lost" in check_meaning_preservation("তিন দিন ব্যথা", "তিন ব্যথা")
    assert check_meaning_preservation("তিন দিন ধরি ব্যতা", "তিন দিন ধরে ব্যথা") == []


def test_guard_detects_invented_symptom():
    g = load_glossary()
    # Input has no vomiting, but normalized text introduces "বমি"
    problems = check_meaning_preservation("আইজ তিন দিন ধরি মাতাত ব্যতা", "আজ তিন দিন ধরে মাথায় ব্যথা সাথে বমি হচ্ছে", g)
    assert "invented_symptom" in problems


def test_llm_output_dropping_negation_is_rejected_after_retry(monkeypatch):
    # LLM fails twice by dropping negation
    llm = FakeLLM(['{"normalized": "ওষুধ খেয়েছি", "uncertain_spans": []}', '{"normalized": "ওষুধ খেয়েছি", "uncertain_spans": []}'])
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: llm)
    out = asyncio.run(normalize("ওষুধ খাই নাই", Settings(), use_llm=True))
    assert out.source == "glossary_only"
    assert out.normalized == "ওষুধ খাইনি"
    assert any("meaning-preservation" in w for w in out.warnings)
    assert llm.calls == 2  # verified 1 retry attempt occurred


def test_llm_retry_recovers_from_initial_failure(monkeypatch):
    # First attempt drops "না", retry preserves "না"
    llm = FakeLLM([
        '{"normalized_text": "ওষুধ খেয়েছি", "changes": [], "uncertain_segments": []}',
        '{"normalized_text": "ওষুধ খাইনি", "changes": [], "uncertain_segments": []}'
    ])
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: llm)
    out = asyncio.run(normalize("ওষুধ খাই নাই", Settings(), use_llm=True))
    assert out.source == "llm_with_glossary"
    assert out.normalized == "ওষুধ খাইনি"
    assert llm.calls == 2


def test_llm_output_adding_invented_symptom_is_rejected(monkeypatch):
    # Mock LLM invents chest pain and vomiting
    llm = FakeLLM(['{"normalized_text": "আজ মাথায় ব্যথা ও বুকে ব্যথা আছে", "changes": [], "uncertain_segments": []}'])
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: llm)
    out = asyncio.run(normalize("মাতাত ব্যতা", Settings(), use_llm=True))
    assert out.source == "glossary_only"
    assert "বুকে ব্যথা" not in out.normalized
    assert any("meaning-preservation" in w for w in out.warnings)


def test_llm_good_output_accepted(monkeypatch):
    llm = FakeLLM(['```json\n{"normalized_text": "আজ তিন দিন ধরে মাথায় ব্যথা", "changes": [{"original": "মাতাত ব্যতা", "normalized": "মাথায় ব্যথা", "reason": "standard head pain", "source": "glossary"}], "uncertain_segments": [{"text": "ব্যতা", "reason": "spelling"}]}\n```'])
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: llm)
    out = asyncio.run(normalize("আইজ তিন দিন ধরি মাতাত ব্যতা", Settings(), use_llm=True))
    assert out.source == "llm_with_glossary" and out.provider == "fake"
    assert "ব্যতা" in out.uncertain_spans
    assert out.changes


def test_llm_invalid_json_falls_back(monkeypatch):
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: FakeLLM(["not json at all"]))
    out = asyncio.run(normalize("মাতাত ব্যতা", Settings(), use_llm=True))
    assert out.source == "glossary_only" and out.warnings


def test_normalization_route_keeps_original(client):
    sid = demo_session(client, "A_ordinary")
    body = client.post("/api/normalization", json={"session_id": sid}).json()
    assert body["source"] in ("cached_demo_output", "demo_prepared", "llm")
    assert body["original"] != body["normalized"]
    assert body["glossary_matches"]  # glossary matching is real, even in demo
    assert "changes" in body
    assert "uncertain_segments" in body


def test_normalization_requires_session(client):
    assert client.post("/api/normalization", json={"session_id": "missing"}).status_code == 404


def test_wrong_session_state_returns_409(client):
    # Session created is in CREATED state; calling normalization without transcribing must be 409
    sid = client.post("/api/session", json={"mode": "live"}).json()["session_id"]
    r = client.post("/api/normalization", json={"session_id": sid})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "WORKFLOW_ORDER_VIOLATION"


def test_glossary_stats_endpoint(client):
    r = client.get("/api/glossary/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total_entries"] >= 35
    assert "sylheti" in data["by_dialect"]
    assert "standard_bangla" in data["by_dialect"]
    assert data["by_dialect"]["sylheti"]["unverified"] > 0
    assert data["by_dialect"]["sylheti"]["verified"] == 0
    assert data["by_dialect"]["standard_bangla"]["verified"] > 0
    assert "disclaimer" in data
