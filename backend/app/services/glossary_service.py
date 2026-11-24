"""Curated dialect glossary: loading, validation, and longest-match lookup."""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from app.schemas.glossary import DialectCount, GlossaryEntry, GlossaryStatsResponse
from app.schemas.normalization import GlossaryMatch

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_BN = "ঀ-৿"
_ZW = dict.fromkeys([0x200C, 0x200D, 0x200B])


def clean_text(text: str) -> str:
    """Normalize Unicode to NFC, remove zero-width characters, and collapse whitespace."""
    text = unicodedata.normalize("NFC", text).translate(_ZW)
    return re.sub(r"\s+", " ", text).strip()


class Glossary:
    def __init__(self, entries: list[dict]):
        self.by_term: dict[str, list[dict]] = {}
        self.entries: list[GlossaryEntry] = []
        for idx, e in enumerate(entries, start=1):
            entry_obj = GlossaryEntry.from_raw(e, idx=idx)
            self.entries.append(entry_obj)
            normalized_reg = clean_text(entry_obj.regional_expression)
            self.by_term.setdefault(normalized_reg, []).append(entry_obj.to_dict())

        # Longest terms first to ensure multi-word expressions win
        terms = sorted(self.by_term.keys(), key=len, reverse=True)
        self._re = (
            re.compile(rf"(?<![{_BN}])(?:" + "|".join(re.escape(t) for t in terms) + rf")(?![{_BN}])")
            if terms
            else None
        )

    def __len__(self) -> int:
        return sum(len(v) for v in self.by_term.values())

    def match(self, text: str) -> list[GlossaryMatch]:
        text = clean_text(text)
        if not self._re:
            return []
        out: list[GlossaryMatch] = []
        for m in self._re.finditer(text):
            entries = self.by_term[m.group(0)]
            first = entries[0]
            matched_term = m.group(0)
            is_multiword = " " in matched_term
            out.append(
                GlossaryMatch(
                    regional=matched_term,
                    standard=first["standard"],
                    english=first["english"],
                    dialect="+".join(dict.fromkeys(e["dialect"] for e in entries)),
                    category=first["category"],
                    verification="verified" if all(e["verification"] == "verified" for e in entries) else "unverified",
                    start=m.start(),
                    end=m.end(),
                    glossary_id=first.get("id"),
                    verification_status=first.get("verification_status") or first.get("verification") or "unverified",
                    matching_method="exact_phrase" if is_multiword else "word_boundary",
                )
            )
        return out

    @staticmethod
    def apply(text: str, matches: list[GlossaryMatch]) -> str:
        text = clean_text(text)
        out, pos = [], 0
        for m in sorted(matches, key=lambda x: x.start):
            out.append(text[pos : m.start])
            out.append(m.standard)
            pos = m.end
        out.append(text[pos:])
        return "".join(out)


STANDARD_FILE = "standard_bangla"


def _dialect_files(include_standard: bool) -> list[Path]:
    d = DATA_DIR / "dialects"
    return sorted(p for p in d.glob("*.json") if include_standard or p.stem != STANDARD_FILE)


@lru_cache
def load_glossary() -> Glossary:
    """Load every regional dialect file in data/dialects (drop a new <dialect>.json to add one)."""
    entries: list[dict] = []
    for path in _dialect_files(include_standard=False):
        data = json.loads(path.read_text(encoding="utf-8"))
        entries.extend(data.get("entries", []))
    return Glossary(entries)


def get_glossary_stats() -> GlossaryStatsResponse:
    """Calculate counts per dialect, verification status, and category distribution."""
    from collections import Counter

    by_dialect: dict[str, DialectCount] = {}
    total_verified = 0
    total_unverified = 0
    overall_categories: Counter[str] = Counter()

    for path in _dialect_files(include_standard=True):
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("entries", [])
        verified = sum(1 for e in entries if (e.get("verification_status") or e.get("verification")) == "verified")
        unverified = len(entries) - verified
        cat_counts = dict(Counter(e.get("category", "common_medical") for e in entries))
        
        by_dialect[path.stem] = DialectCount(
            total=len(entries),
            verified=verified,
            unverified=unverified,
            by_category=cat_counts,
        )
        if path.stem != STANDARD_FILE:  # the standard list is a reference, not dialect coverage
            total_verified += verified
            total_unverified += unverified
            for cat, count in cat_counts.items():
                overall_categories[cat] += count

    return GlossaryStatsResponse(
        total_entries=total_verified + total_unverified,
        by_dialect=by_dialect,
        verified_total=total_verified,
        unverified_total=total_unverified,
        by_category=dict(overall_categories),
        disclaimer=(
            "Dialect entries marked verified were reviewed by named team members (see verified_by); "
            "this is a text-level review, not independent linguistic validation, and the glossary has "
            "not been tested on real speech. Standard Bangla entries are a reference list."
        ),
    )
