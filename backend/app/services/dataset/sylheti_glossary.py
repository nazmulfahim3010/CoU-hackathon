"""Sylheti 120-entry glossary loader, validator, and JSON synchronizer."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from app.schemas.glossary import GlossaryEntry


def find_glossary_csv_path() -> Path | None:
    """Find sylheti_glossary_120-final.csv across project roots."""
    possible = [
        Path("data/glossary/sylheti_glossary_120-final.csv"),
        Path("../data/glossary/sylheti_glossary_120-final.csv"),
        Path("backend/app/data/glossary/sylheti_glossary_120-final.csv"),
        Path("app/data/glossary/sylheti_glossary_120-final.csv"),
        Path("dataset/Audio_Record_and_Csv/sylheti_glossary_120-final.csv"),
        Path("../dataset/Audio_Record_and_Csv/sylheti_glossary_120-final.csv"),
        Path(__file__).resolve().parents[4] / "data" / "glossary" / "sylheti_glossary_120-final.csv",
        Path(__file__).resolve().parents[3] / "data" / "glossary" / "sylheti_glossary_120-final.csv",
        Path(__file__).resolve().parents[2] / "data" / "glossary" / "sylheti_glossary_120-final.csv",
    ]
    for p in possible:
        if p.is_file():
            return p.resolve()
    return None


def parse_sylheti_glossary_csv(csv_path: Path | str) -> list[GlossaryEntry]:
    """Parse sylheti_glossary_120-final.csv cleanly into GlossaryEntry models."""
    path = Path(csv_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Sylheti glossary CSV not found at {path}")

    entries: list[GlossaryEntry] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            if not any(row.values()):
                continue
            entry = GlossaryEntry.from_raw(row, default_dialect="sylheti", idx=idx)
            entries.append(entry)

    return entries


def sync_glossary_json(csv_path: Path | str, json_path: Path | str) -> int:
    """Sync the parsed CSV into backend/app/data/dialects/sylheti.json."""
    entries = parse_sylheti_glossary_csv(csv_path)
    jpath = Path(json_path).resolve()
    jpath.parent.mkdir(parents=True, exist_ok=True)

    verified_count = sum(1 for e in entries if e.verification_status == "verified")
    data = {
        "dialect": "sylheti",
        "status": (
            "TEAM-VERIFIED - all entries reviewed by named team members; not tested on real speech"
            if verified_count == len(entries)
            else f"PARTLY VERIFIED - {verified_count}/{len(entries)} verified"
        ),
        "entries": [e.to_dict() for e in entries],
    }
    jpath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(entries)


def get_sylheti_glossary_stats(entries: list[GlossaryEntry] | None = None) -> dict:
    """Return verified statistics and category counts for Sylheti glossary."""
    if entries is None:
        csv_path = find_glossary_csv_path()
        if csv_path:
            entries = parse_sylheti_glossary_csv(csv_path)
        else:
            entries = []

    total = len(entries)
    verified = sum(1 for e in entries if e.verification_status == "verified")
    unverified = total - verified
    categories = Counter(e.category for e in entries)

    return {
        "dialect": "sylheti",
        "total": total,
        "verified": verified,
        "unverified": unverified,
        "by_category": dict(categories),
    }
