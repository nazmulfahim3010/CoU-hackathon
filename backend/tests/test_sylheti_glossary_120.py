"""Tests for Sylheti 120-entry glossary integration, matching rules, and audit metadata."""
from pathlib import Path
import pytest

from app.schemas.normalization import GlossaryMatch, NormalizationChange
from app.services.dataset.sylheti_glossary import (
    find_glossary_csv_path,
    get_sylheti_glossary_stats,
    parse_sylheti_glossary_csv,
    sync_glossary_json,
)
from app.services.glossary_service import (
    Glossary,
    get_glossary_stats,
    load_glossary,
)


def test_sylheti_glossary_csv_loading():
    """Verify sylheti_glossary_120-final.csv exists and loads exactly 120 entries."""
    csv_path = find_glossary_csv_path()
    assert csv_path is not None, "Sylheti glossary CSV path not found"
    entries = parse_sylheti_glossary_csv(csv_path)
    assert len(entries) == 120, f"Expected 120 entries, found {len(entries)}"

    # Check required fields on all entries
    for e in entries:
        assert e.id.startswith("syl_"), f"Invalid ID format: {e.id}"
        assert e.regional_expression, f"Missing regional expression in {e.id}"
        assert e.standard_bangla, f"Missing standard bangla in {e.id}"
        assert e.english_meaning, f"Missing english meaning in {e.id}"
        assert e.dialect == "sylheti"
        assert e.verification_status == "verified"
        assert e.verified_by in ("Fahim", "Noyon")


def test_sylheti_glossary_stats_coverage():
    """Verify statistics helper and endpoint data report 120 verified entries."""
    stats = get_glossary_stats()
    assert "sylheti" in stats.by_dialect
    syl = stats.by_dialect["sylheti"]
    assert syl.total == 120
    assert syl.verified == 120
    assert syl.unverified == 0
    assert "pain_description" in syl.by_category
    assert "symptom" in syl.by_category
    assert "common_medical" in syl.by_category


def test_longest_match_first_resolution():
    """Verify multi-word phrase wins over sub-phrases and single words."""
    glossary = load_glossary()
    
    # "বুকর বাম সাইডে বেদনা" (syl_010) vs "বুক বেদনা" (syl_009) vs "বেদনা" (syl_011)
    text = "আমার হাঁটার সময় বুকর বাম সাইডে বেদনা উটে"
    matches = glossary.match(text)
    
    # The longest phrase "বুকর বাম সাইডে বেদনা" must be matched, not just "বেদনা"
    matched_regionals = [m.regional for m in matches]
    assert "বুকর বাম সাইডে বেদনা" in matched_regionals
    assert "বেদনা" not in matched_regionals
    
    match_obj = next(m for m in matches if m.regional == "বুকর বাম সাইডে বেদনা")
    assert match_obj.standard == "বাম পাশে বুকে ব্যথা"
    assert match_obj.glossary_id == "syl_010"
    assert match_obj.matching_method == "exact_phrase"
    assert match_obj.verification_status == "verified"


def test_single_word_boundary_matching():
    """Verify single-word match records word_boundary matching_method."""
    glossary = load_glossary()
    text = "আমার শরীরে খুব বেদনা"
    matches = glossary.match(text)
    matched = next((m for m in matches if m.regional == "বেদনা"), None)
    assert matched is not None
    assert matched.glossary_id == "syl_011"
    assert matched.standard == "ব্যথা"
    assert matched.matching_method == "word_boundary"


def test_normalization_change_audit_fields():
    """Verify NormalizationChange model captures all audit trail fields."""
    change = NormalizationChange(
        original="দম বন্ধ অইজার",
        normalized="দম বন্ধ হয়ে আসছে",
        reason="Glossary match (symptom)",
        source="glossary",
        glossary_id="syl_018",
        category="symptom",
        verification_status="verified",
        matching_method="exact_phrase",
    )
    assert change.glossary_id == "syl_018"
    assert change.category == "symptom"
    assert change.verification_status == "verified"
    assert change.matching_method == "exact_phrase"
