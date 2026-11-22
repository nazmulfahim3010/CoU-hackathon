import asyncio

from app.config import Settings
from app.services import dialect_normalizer
from app.services.dialect_normalizer import check_meaning_preservation, count_negations, normalize
from app.services.glossary_service import Glossary, load_glossary
from conftest import FakeLLM, demo_session


def test_glossary_loads_entries_with_required_fields():
    g = load_glossary()
    assert len(g) >= 20
    for entries in g.by_term.values():
        for e in entries:
            for key in ("regional", "standard", "english", "dialect", "category", "example", "verification", "source"):
                assert key in e
            assert e["verification"] == "unverified"  # nothing is claimed as verified


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


def test_llm_output_dropping_negation_is_rejected(monkeypatch):
    llm = FakeLLM(['{"normalized": "ওষুধ খেয়েছি", "uncertain_spans": []}'])
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: llm)
    out = asyncio.run(normalize("ওষুধ খাই নাই", Settings(), use_llm=True))
    assert out.source == "glossary_only"
    assert out.normalized == "ওষুধ খাইনি"
    assert any("meaning-preservation" in w for w in out.warnings)


def test_llm_good_output_accepted(monkeypatch):
    llm = FakeLLM(['```json\n{"normalized": "আজ তিন দিন ধরে মাথায় ব্যথা", "uncertain_spans": ["ব্যতা"]}\n```'])
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: llm)
    out = asyncio.run(normalize("আইজ তিন দিন ধরি মাতাত ব্যতা", Settings(), use_llm=True))
    assert out.source == "llm_with_glossary" and out.provider == "fake"
    assert "ব্যতা" in out.uncertain_spans


def test_llm_invalid_json_falls_back(monkeypatch):
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: FakeLLM(["not json at all"]))
    out = asyncio.run(normalize("মাতাত ব্যতা", Settings(), use_llm=True))
    assert out.source == "glossary_only" and out.warnings


def test_normalization_route_keeps_original(client):
    sid = demo_session(client, "A_ordinary")
    body = client.post("/api/normalization", json={"session_id": sid}).json()
    assert body["source"] == "demo_prepared"
    assert body["original"] != body["normalized"]
    assert body["glossary_matches"]  # glossary matching is real, even in demo


def test_normalization_requires_session(client):
    assert client.post("/api/normalization", json={"session_id": "missing"}).status_code == 404
