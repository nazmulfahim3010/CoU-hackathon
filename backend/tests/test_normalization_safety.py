"""Normalization safety: guard regressions found on real Sylheti data, LLM-proposal verification, provider outage,
original-transcript immutability, and one engine for typed and recognised text."""
import asyncio
import json

import pytest

from app.config import Settings
from app.core.exceptions import KothaError
from app.services import dialect_normalizer
from app.services.dialect_normalizer import check_meaning_preservation, count_negations, normalize
from conftest import FakeLLM, FakeSTT, requires_ffmpeg
from test_sylheti_audio_dataset import write_wav

S = Settings(_env_file=None)


# ---------------------------------------------------------------- negation heuristic regression
@pytest.mark.parametrize("noun", ["পানি", "জানি", "চুলকানি", "খিঁচুনি", "চিনি", "খাজানি", "জিরানি", "কাওয়ানি", "আমদানি"])
def test_nouns_ending_in_ni_are_not_negations(noun):
    assert count_negations(noun) == 0


@pytest.mark.parametrize("verb", ["করিনি", "খাইনি", "হয়নি", "আসেনি", "বুঝিনি", "দেখাইনি", "হইছেনি", "পারি না", "নেই", "নাই"])
def test_real_negations_are_still_counted(verb):
    assert count_negations(verb) == 1


def test_itching_noun_does_not_cause_a_false_negation_failure():
    assert check_meaning_preservation("খাবার খাইলে আমার খুব খাজানি অইসে", "খাবার খেলে আমার খুব চুলকানি হয়েছে") == []


# ---------------------------------------------------------------- invented-symptom guard regression
def test_dialect_headache_phrase_is_not_flagged_as_invention():
    assert check_meaning_preservation("আমার মাথা বেদনা করের", "আমার মাথা ব্যথা করছে") == []


@pytest.mark.parametrize("bad", ["আমার মাথা ব্যথা এবং বুকে ব্যথা", "আমার মাথা ব্যথা এবং বমি", "আমার মাথা ব্যথা ও পেট ব্যথা"])
def test_real_symptom_insertions_are_still_rejected(bad):
    assert "invented_symptom" in check_meaning_preservation("আমার মাথা বেদনা করের", bad)


# ---------------------------------------------------------------- LLM proposals are verified independently
def reply(normalized, changes):
    return json.dumps({"normalized_text": normalized, "changes": changes, "uncertain_segments": []}, ensure_ascii=False)


def test_llm_change_citing_text_not_in_the_transcript_is_dropped(monkeypatch):
    llm = FakeLLM([reply("আমার মাথা ব্যথা করছে", [
        {"original": "মাথা বেদনা", "normalized": "মাথা ব্যথা", "reason": "x", "source": "llm"},
        {"original": "ফোন নম্বর", "normalized": "অন্য কিছু", "reason": "made up", "source": "llm"}])])
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: llm)
    out = asyncio.run(normalize("আমার মাথা বেদনা করের", S, use_llm=True))
    assert out.normalization_status == "llm_proposal_validated"
    assert [c.original for c in out.changes] == ["মাথা বেদনা"]
    assert any("not in the transcript" in w for w in out.warnings)


def test_change_falsely_labelled_glossary_is_relabelled_and_gets_real_evidence(monkeypatch):
    llm = FakeLLM([reply("আমার মাথা ব্যথা করছে", [{"original": "মাথা বেদনা", "normalized": "মাথা ব্যথা", "reason": "x", "source": "glossary"}])])
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: llm)
    out = asyncio.run(normalize("আমার মাথা বেদনা করের", S, use_llm=True))
    [c] = out.changes
    assert c.source == "llm"  # there is no glossary row for the whole phrase "মাথা বেদনা"
    assert c.glossary_evidence_ids == ["syl_011"]  # the one real row that contributed: বেদনা -> ব্যথা
    assert any("no matching glossary entry" in w for w in out.warnings)


def test_llm_that_drops_a_negation_is_rejected_and_the_glossary_proposal_is_shown(monkeypatch):
    llm = FakeLLM([reply("আজ সকাল থেকে আমার জ্বর আছে", [])])
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: llm)
    out = asyncio.run(normalize("আইজ সকাল থাকি আমার আর জ্বর নাই", S, use_llm=True))
    assert out.normalization_status == "llm_rejected_glossary_fallback" and out.source == "glossary_only"
    assert "জ্বর আছে" not in out.normalized and "নেই" in out.normalized
    assert any("failed meaning-preservation" in w for w in out.warnings)


def test_llm_that_inserts_a_symptom_is_rejected(monkeypatch):
    llm = FakeLLM([reply("আমার মাথা ব্যথা এবং বুকে ব্যথা", [])])
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: llm)
    out = asyncio.run(normalize("আমার মাথা বেদনা করের", S, use_llm=True))
    assert out.normalization_status == "llm_rejected_glossary_fallback" and "বুকে" not in out.normalized


@pytest.mark.parametrize("bad_reply", ["not json at all", "{}", '{"normalized_text": ""}'])
def test_invalid_llm_output_falls_back_without_crashing(monkeypatch, bad_reply):
    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: FakeLLM([bad_reply]))
    out = asyncio.run(normalize("আমার মাথা বেদনা করের", S, use_llm=True))
    assert out.normalization_status == "llm_rejected_glossary_fallback" and out.warnings


def test_llm_provider_outage_never_blocks_the_patient(monkeypatch):
    class Down:
        name = "down"

        async def complete(self, system, user, max_tokens=1500):
            raise KothaError(502, "PROVIDER_ERROR", "HTTP 404 model not found")

    monkeypatch.setattr(dialect_normalizer, "get_llm", lambda s: Down())
    text = "আমার মাথা বেদনা করের"
    out = asyncio.run(normalize(text, S, use_llm=True))
    assert out.original == text  # the original is preserved verbatim
    assert out.source == "glossary_only" and out.normalization_status == "llm_rejected_glossary_fallback"
    assert any("PROVIDER_ERROR" in w for w in out.warnings) and "model not found" not in " ".join(out.warnings)


def test_original_transcript_is_never_overwritten():
    text = "  আমার   মাথাত  বেদনা করের  "
    out = asyncio.run(normalize(text, S, use_llm=False))
    assert out.original == text and out.original_text == text and out.normalized != text


# ---------------------------------------------------------------- one engine for typed and recognised text
def new_live_session(client):
    return client.post("/api/session", json={"mode": "live"}).json()["session_id"]


TEXT = "গত রাইত থাকি আমার বুক বেদনা করের"


def test_typed_text_uses_the_same_engine_as_direct_normalization(client):
    sid = new_live_session(client)
    assert client.post("/api/transcription/typed", json={"session_id": sid, "text": TEXT, "dialect_hint": "sylheti"}).status_code == 200
    body = client.post("/api/normalization", json={"session_id": sid}).json()
    direct = asyncio.run(normalize(TEXT, S, use_llm=False))
    assert body["normalized"] == direct.normalized
    assert [e["glossary_id"] for e in body["glossary_evidence"]] == [e.glossary_id for e in direct.glossary_evidence] == ["syl_009"]
    assert body["normalization_status"] == "glossary_only_proposal"


@requires_ffmpeg
def test_recognised_text_uses_the_same_engine_as_typed_text(client, monkeypatch, tmp_path):
    wav = tmp_path / "r.wav"
    write_wav(wav, 2.0, rate=16000)
    monkeypatch.setattr("app.api.routes.transcription.get_stt", lambda s: FakeSTT(TEXT))
    sid_audio = client.post("/api/transcription", files={"audio": ("r.wav", wav.read_bytes(), "audio/wav")}).json()["session_id"]
    from_audio = client.post("/api/normalization", json={"session_id": sid_audio}).json()

    sid_typed = new_live_session(client)
    client.post("/api/transcription/typed", json={"session_id": sid_typed, "text": TEXT})
    from_typed = client.post("/api/normalization", json={"session_id": sid_typed}).json()
    for key in ("original", "normalized", "glossary_evidence", "normalization_status", "changes"):
        assert from_audio[key] == from_typed[key], key


def test_clinical_extraction_is_impossible_before_confirmation_for_live_text(client):
    sid = new_live_session(client)
    client.post("/api/transcription/typed", json={"session_id": sid, "text": TEXT})
    client.post("/api/normalization", json={"session_id": sid})
    r = client.post("/api/clinical/extract", json={"session_id": sid})
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFIRMATION_REQUIRED"
