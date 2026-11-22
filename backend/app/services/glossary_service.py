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
            out.append(
                GlossaryMatch(
                    regional=m.group(0),
                    standard=first["standard"],
                    english=first["english"],
                    dialect="+".join(dict.fromkeys(e["dialect"] for e in entries)),
                    category=first["category"],
                    verification="verified" if all(e["verification"] == "verified" for e in entries) else "unverified",
                    start=m.start(),
                    end=m.end(),
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


@lru_cache
def load_glossary() -> Glossary:
    entries: list[dict] = []
    for name in ("sylheti", "chittagonian", "noakhali"):
        path = DATA_DIR / "dialects" / f"{name}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            entries.extend(data.get("entries", []))
    return Glossary(entries)


def get_glossary_stats() -> GlossaryStatsResponse:
    """Calculate counts per dialect and verification status."""
    by_dialect: dict[str, DialectCount] = {}
    total_verified = 0
    total_unverified = 0

    for name in ("sylheti", "chittagonian", "noakhali", "standard_bangla"):
        path = DATA_DIR / "dialects" / f"{name}.json"
        if not path.exists():
            by_dialect[name] = DialectCount(total=0, verified=0, unverified=0)
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("entries", [])
        verified = sum(1 for e in entries if (e.get("verification_status") or e.get("verification")) == "verified")
        unverified = sum(1 for e in entries if (e.get("verification_status") or e.get("verification")) != "verified")
        by_dialect[name] = DialectCount(total=len(entries), verified=verified, unverified=unverified)
        total_verified += verified
        total_unverified += unverified

    return GlossaryStatsResponse(
        total_entries=total_verified + total_unverified,
        by_dialect=by_dialect,
        verified_total=total_verified,
        unverified_total=total_unverified,
        disclaimer="Regional dialect entries are unverified drafts awaiting native speaker review. Standard Bangla entries are reference standard.",
    )
