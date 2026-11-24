"""Evaluation metrics and the evaluate_sylheti_dataset script (no real provider, no real recordings)."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from app.services.dataset import evaluation as ev
from app.services.dataset.metrics import cer, edit_distance, exact_match, prepare, wer
from app.services.glossary_service import load_glossary
from test_sylheti_audio_dataset import HEADER, CSV_NAME, make, row, write_wav


# ---------------------------------------------------------------- metrics
def test_edit_distance_basics():
    assert edit_distance("kitten", "sitting") == 3
    assert edit_distance([], [1, 2]) == 2 and edit_distance([1, 2], []) == 2 and edit_distance([1], [1]) == 0


def test_wer_and_cer_known_values():
    assert wer("আমার জ্বর আছে", "আমার জ্বর নেই") == pytest.approx(1 / 3)
    assert wer("আমার জ্বর আছে", "আমার জ্বর আছে") == 0
    assert wer("এক দুই", "") == 1.0 and wer("", "") == 0.0 and wer("", "কিছু") == 1.0
    assert cer("জ্বর", "জার") > 0 and cer("জ্বর", "জ্বর") == 0
    assert cer("abcd", "abxd") == pytest.approx(0.25)


def test_scoring_ignores_punctuation_and_spacing_only():
    assert exact_match("আমার জ্বর, আছে।", "আমার   জ্বর আছে")
    assert not exact_match("আমার জ্বর আছে", "আমার জ্বর নেই")
    assert prepare("  এক।  দুই, ") == "এক দুই"


def test_asr_metrics_flags_empty_transcripts():
    assert ev.asr_metrics("আমার জ্বর", "")["empty_transcript"] is True
    m = ev.asr_metrics("আমার জ্বর", "আমার জ্বর")
    assert m == {"cer": 0.0, "wer": 0.0, "exact_match": True, "empty_transcript": False}


# ---------------------------------------------------------------- semantic screen
G = load_glossary()
ORIG = "আমার মাথা বেদনা করের, জ্বর নাই"
REF = "আমার মাথাব্যথা হচ্ছে, জ্বর নেই"


def test_faithful_normalization_passes_the_screen():
    r = ev.semantic_checks(ORIG, "আমার মাথা ব্যথা করছে, জ্বর নেই", REF, G)
    assert r["guard_problems"] == [] and r["unsupported_symptom_groups"] == []
    assert r["negation_count_matches_reference"] and r["symptom_groups_missing_vs_reference"] == []


def test_dropped_negation_is_flagged():
    r = ev.semantic_checks(ORIG, "আমার মাথা ব্যথা করছে, জ্বর আছে", REF, G)
    assert "negation_changed" in r["guard_problems"] and not r["negation_count_matches_reference"] and r["requires_human_review"]


def test_invented_symptom_is_flagged():
    r = ev.semantic_checks(ORIG, "আমার মাথা ব্যথা এবং বুকে ব্যথা করছে, জ্বর নেই", REF, G)
    assert "chest_pain" in r["unsupported_symptom_groups"] and "chest_pain" in r["symptom_groups_extra_vs_reference"]
    assert r["requires_human_review"]


def test_missing_symptom_and_lost_number_are_flagged():
    r = ev.semantic_checks("৩ দিন থাকি আমার জ্বর আর কাওয়ানি", "আমার জ্বর", "তিন দিন ধরে আমার জ্বর ও কাশি", G)
    assert "cough" in r["symptom_groups_missing_vs_reference"] and not r["numbers_match_reference"]


def test_far_from_reference_always_needs_a_human():
    r = ev.semantic_checks("আমার জ্বর", "সম্পূর্ণ অন্য একটি বাক্য এখানে আছে", "আমার জ্বর", G)
    assert r["wer_vs_reference"] > ev.WER_REVIEW_THRESHOLD and r["requires_human_review"]


# ---------------------------------------------------------------- label-mismatch diagnostic (dataset never altered)
def test_swapped_pair_is_detected_as_a_possible_label_mismatch():
    refs = {"rec_015": "আমার মাথায় ব্যথা আছে অনেকদিন ধরে", "rec_016": "ডায়াবেটিস আছে এবং শরীর দুর্বল লাগে"}
    hyps = {"rec_015": refs["rec_016"], "rec_016": refs["rec_015"]}  # audio of each is the other row's sentence
    out = ev.possible_label_mismatches(hyps, refs)
    assert {m["recording_id"]: m["closer_to"] for m in out} == {"rec_015": "rec_016", "rec_016": "rec_015"}
    assert ev.possible_label_mismatches(refs, refs) == []  # correct labels: nothing flagged


# ---------------------------------------------------------------- rollups
def test_rollups_count_failures_and_scenarios():
    rows = [
        {"recording_id": "r1", "scenario_card": "A1", "status": "ok", "processing_seconds": 1.0,
         "asr": {"cer": 0.2, "wer": 0.4, "exact_match": False, "empty_transcript": False},
         "normalization_of_reference": {"requires_human_review": True}},
        {"recording_id": "r2", "scenario_card": "A1", "status": "failed", "processing_seconds": 0.5, "error_code": "ASR_TIMEOUT",
         "normalization_of_reference": {"requires_human_review": False}},
        {"recording_id": "r3", "scenario_card": "B1", "status": "ok", "processing_seconds": 3.0,
         "asr": {"cer": 0.0, "wer": 0.0, "exact_match": True, "empty_transcript": False},
         "normalization_of_reference": {"requires_human_review": False}},
    ]
    a = ev.asr_rollup(rows)
    assert a["successful_transcriptions"] == 2 and a["failed_transcriptions"] == 1 and a["failure_rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert a["mean_cer"] == 0.1 and a["exact_match_rate"] == pytest.approx(1 / 3, abs=1e-4)
    s = ev.by_scenario(rows)
    assert s["A1"]["recordings"] == 2 and s["A1"]["failed_transcriptions"] == 1 and s["A1"]["normalization_needing_human_review"] == 1
    assert s["B1"]["mean_wer"] == 0.0


# ---------------------------------------------------------------- the script
def load_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_sylheti_dataset.py"
    spec = importlib.util.spec_from_file_location("evaluate_sylheti_dataset", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["evaluate_sylheti_dataset"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def small_dataset(tmp_path):
    d = tmp_path / "ds"
    (d / "recordings").mkdir(parents=True)
    write_wav(d / "recordings" / "a.wav", 1.0)
    write_wav(d / "recordings" / "b.wav", 1.0)
    make(d, [row("rec_001", "a.wav", transcript="আমার জ্বর নাই"), row("rec_002", "b.wav", transcript="আমার মাথাত বেদনা করের", scenario_card="B1")])
    return d


def run_script(mod, monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["evaluate_sylheti_dataset.py", *argv])
    return mod.main()


def test_script_refuses_to_send_audio_without_explicit_confirmation(monkeypatch, small_dataset, tmp_path, capsys):
    mod = load_script()
    assert run_script(mod, monkeypatch, ["--dataset-dir", str(small_dataset), "--out-dir", str(tmp_path / "out")]) == 2
    assert "Refusing to run" in capsys.readouterr().out
    assert not (tmp_path / "out").exists()  # nothing written, nothing sent


def test_skip_asr_evaluates_normalization_without_any_provider(monkeypatch, small_dataset, tmp_path):
    mod = load_script()
    out = tmp_path / "out"
    assert run_script(mod, monkeypatch, ["--skip-asr", "--no-llm", "--dataset-dir", str(small_dataset), "--out-dir", str(out)]) == 0
    norm = json.loads((out / "sylheti_normalization_evaluation.json").read_text(encoding="utf-8"))
    assert norm["reference_transcripts_normalized"]["pairs_evaluated"] == 2 and norm["asr_run"] is False
    asr = json.loads((out / "sylheti_asr_evaluation.json").read_text(encoding="utf-8"))
    assert asr["aggregate"] is None and asr["third_party_audio_processing_confirmed"] is False


def test_asr_text_comes_from_the_stt_adapter_never_from_the_reference(monkeypatch, small_dataset, tmp_path):
    mod = load_script()
    monkeypatch.setattr(mod, "stt_configured", lambda s: True)
    calls = []

    async def fake_transcribe(settings, record):
        calls.append(record.recording_id)
        if record.recording_id == "rec_001":
            return "আমার জ্বর আছে", 0.2, None  # differs from the reference on purpose
        return None, 0.1, "ASR_TIMEOUT"

    monkeypatch.setattr(mod, "transcribe_one", fake_transcribe)
    out = tmp_path / "out"
    rc = run_script(mod, monkeypatch, ["--confirm-third-party-processing", "--no-llm", "--delay", "0", "--dataset-dir", str(small_dataset), "--out-dir", str(out)])
    assert rc == 0 and calls == ["rec_001", "rec_002"]

    asr = json.loads((out / "sylheti_asr_evaluation.json").read_text(encoding="utf-8"))
    agg = asr["aggregate"]
    assert agg["successful_transcriptions"] == 1 and agg["failed_transcriptions"] == 1 and agg["failure_rate"] == 0.5
    rec1 = next(r for r in asr["recordings"] if r["recording_id"] == "rec_001")
    assert rec1["asr"]["exact_match"] is False and rec1["asr"]["wer"] > 0  # scored against the original, not copied from it
    rec2 = next(r for r in asr["recordings"] if r["recording_id"] == "rec_002")
    assert rec2["status"] == "failed" and rec2["error_code"] == "ASR_TIMEOUT" and "asr" not in rec2  # no invented fallback text

    local = json.loads((out / "sylheti_evaluation.local.json").read_text(encoding="utf-8"))
    assert next(x for x in local if x["recording_id"] == "rec_001")["asr_transcript"] == "আমার জ্বর আছে"
    assert "asr_transcript" not in next(x for x in local if x["recording_id"] == "rec_002")


def test_public_reports_contain_no_text_names_paths_or_keys(monkeypatch, small_dataset, tmp_path):
    mod = load_script()
    monkeypatch.setattr(mod, "stt_configured", lambda s: True)

    async def fake(settings, record):
        return "আমার জ্বর আছে", 0.1, None

    monkeypatch.setattr(mod, "transcribe_one", fake)
    out = tmp_path / "out"
    run_script(mod, monkeypatch, ["--confirm-third-party-processing", "--no-llm", "--delay", "0", "--dataset-dir", str(small_dataset), "--out-dir", str(out)])
    for name in ("sylheti_asr_evaluation.json", "sylheti_normalization_evaluation.json", "sylheti_asr_evaluation.md"):
        text = (out / name).read_text(encoding="utf-8")
        for secret in ("আমার জ্বর", "আমার মাথাত", "Speaker One", "a.wav", str(small_dataset), "api_key", "Bearer"):
            assert secret not in text, (name, secret)
    assert "আমার জ্বর" in (out / "sylheti_evaluation.local.json").read_text(encoding="utf-8")  # texts only in the git-ignored file
