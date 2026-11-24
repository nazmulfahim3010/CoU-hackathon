"""Sylheti glossary CSV (controlled lexical resource): validation, runtime consistency, evidence tracking."""
import asyncio
import csv
import json

import pytest

from app.config import Settings
from app.services.dataset.glossary_csv import (
    DEFAULT_GLOSSARY_CSV, REQUIRED_COLUMNS, compare_with_runtime, load_glossary_csv,
)
from app.services.dialect_normalizer import normalize
from app.services.glossary_service import DATA_DIR, Glossary, load_glossary


@pytest.fixture(scope="module")
def real():
    return load_glossary_csv(DEFAULT_GLOSSARY_CSV)


def test_real_csv_loads_120_clean_entries(real):
    s = real.summary()
    assert s["entries_loaded"] == 120 and s["unique_ids"] == 120 and s["unique_expressions"] == 120
    assert s["errors"] == 0 and s["dialects"] == {"sylheti": 120}
    assert set(s["verification_status"]) == {"verified"}
    assert {"symptom", "common_medical", "time_expression", "body_part", "pain_description", "fever", "severity"} == set(s["categories"])


def test_verification_metadata_is_preserved_verbatim(real):
    for e in real.entries:
        assert e["verified_by"] and e["verification_date"] and e["verification_note"]
        assert e["source"] and e["contributor"]


def test_runtime_glossary_matches_the_source_csv_exactly(real):
    runtime = json.loads((DATA_DIR / "dialects" / "sylheti.json").read_text(encoding="utf-8"))["entries"]
    assert compare_with_runtime(real.entries, runtime) == []


def test_drift_is_detected():
    entries = [{"id": "syl_001", "regional_expression": "নায়", "standard_bangla": "না", "category": "common_medical",
                "example_sentence": "x", "verification_status": "verified", "verified_by": "A", "verification_date": "d", "verification_note": "n"}]
    runtime = [dict(entries[0], standard_bangla="হ্যাঁ")]  # someone edited the runtime copy
    issues = compare_with_runtime(entries, runtime)
    assert any(i.code == "RUNTIME_MISMATCH" for i in issues)
    assert any(i.code == "RUNTIME_MISSING_ENTRY" for i in compare_with_runtime(entries, []))
    assert any(i.code == "RUNTIME_EXTRA_ENTRY" for i in compare_with_runtime([], runtime))


def write_csv(path, rows, columns=REQUIRED_COLUMNS):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def good(i="syl_001", expr="নায়", **over):
    r = {"id": i, "regional_expression": expr, "standard_bangla": "না", "english_meaning": "no", "dialect": "sylheti",
         "category": "common_medical", "example_sentence": "x", "source": "s", "contributor": "c",
         "verification_status": "verified", "verified_by": "A", "verification_date": "2026-01-01", "verification_note": "n"}
    r.update(over)
    return r


def test_invalid_rows_are_rejected_and_reported(tmp_path):
    p = tmp_path / "g.csv"
    write_csv(p, [
        good("syl_001", "নায়"),
        good("syl_001", "নাই"),                          # duplicate id
        good("syl_003", "নায়"),                          # duplicate expression
        good("syl_004", "abc"),                           # no Bengali script
        good("syl_005", "ব্যথা", category="mystery"),     # unknown category
        good("syl_006", "জ্বর", dialect="chittagonian"),  # wrong dialect
        good("syl_007", "কাশি", verification_status="maybe"),
        good("syl_008", "বমি", standard_bangla=""),       # missing value
    ])
    r = load_glossary_csv(p)
    found = {i.code for i in r.issues}
    for code in ("GLOSSARY_DUPLICATE_ID", "GLOSSARY_DUPLICATE_EXPRESSION", "GLOSSARY_NOT_BENGALI", "GLOSSARY_CATEGORY",
                 "GLOSSARY_DIALECT", "GLOSSARY_STATUS", "GLOSSARY_MISSING_VALUE"):
        assert code in found, code
    assert [e["id"] for e in r.entries] == ["syl_001"]  # only the valid row survives


def test_missing_file_and_missing_columns(tmp_path):
    assert [i.code for i in load_glossary_csv(tmp_path / "nope.csv").issues] == ["GLOSSARY_NOT_FOUND"]
    write_csv(tmp_path / "g.csv", [good()], columns=("id", "regional_expression"))
    assert [i.code for i in load_glossary_csv(tmp_path / "g.csv").issues] == ["GLOSSARY_MISSING_COLUMNS"]


def test_unverified_status_is_never_silently_promoted(tmp_path):
    write_csv(tmp_path / "g.csv", [good(verification_status="unverified", verified_by="", verification_date="", verification_note="")])
    e = load_glossary_csv(tmp_path / "g.csv").entries[0]
    assert e["verification_status"] == "unverified"
    g = Glossary([{**e, "regional": e["regional_expression"], "standard": e["standard_bangla"], "english": e["english_meaning"],
                   "verification": e["verification_status"]}])
    assert g.match("আইজ নায়")[0].verification == "unverified"


def test_csv_is_not_modified_by_loading(real):
    before = DEFAULT_GLOSSARY_CSV.read_bytes()
    load_glossary_csv(DEFAULT_GLOSSARY_CSV)
    load_glossary()
    assert DEFAULT_GLOSSARY_CSV.read_bytes() == before


# ---------------------------------------------------------------- evidence tracking in the matcher
def test_matches_carry_glossary_id_and_matching_method():
    g = load_glossary()
    [m] = g.match("গত রাইত থাকি আমার বুক বেদনা করের")
    assert m.regional == "বুক বেদনা" and m.glossary_id == "syl_009" and m.matching_method == "exact_phrase"
    assert m.category == "pain_description" and m.verification == "verified"
    [w] = g.match("আমার বেদনা")
    assert w.glossary_id == "syl_011" and w.matching_method == "exact_word"


def test_multiword_phrase_wins_over_its_components():
    g = load_glossary()
    assert [m.regional for m in g.match("বুক বেদনা")] == ["বুক বেদনা"]  # not just "বেদনা"
    assert [m.glossary_id for m in g.match("হাত পা সলের না")] == ["syl_025"]


def test_normalization_response_traces_every_applied_entry():
    out = asyncio.run(normalize("গত রাইত থাকি আমার বুক বেদনা করের", Settings(_env_file=None), use_llm=False))
    assert out.normalization_status == "glossary_only_proposal"
    [ev] = out.glossary_evidence
    assert (ev.glossary_id, ev.regional_expression, ev.standard_bangla, ev.category, ev.verification_status, ev.matching_method, ev.applied) == (
        "syl_009", "বুক বেদনা", "বুকে ব্যথা", "pain_description", "verified", "exact_phrase", True)
    assert out.changes[0].glossary_evidence_ids == ["syl_009"]


def test_unmatched_text_is_unchanged_and_says_so():
    text = "আমার একটা সমস্যা আছে"
    out = asyncio.run(normalize(text, Settings(_env_file=None), use_llm=False))
    assert out.normalized == text and out.normalization_status == "no_glossary_match_unchanged" and out.glossary_evidence == []
