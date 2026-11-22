"""Curated dialect glossary: loading and longest-match lookup."""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from app.schemas.normalization import GlossaryMatch

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_BN = "ঀ-৿"
_ZW = dict.fromkeys([0x200C, 0x200D, 0x200B])


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).translate(_ZW)
    return re.sub(r"\s+", " ", text).strip()


class Glossary:
    def __init__(self, entries: list[dict]):
        self.by_term: dict[str, list[dict]] = {}
        for e in entries:
            self.by_term.setdefault(unicodedata.normalize("NFC", e["regional"]), []).append(e)
        terms = sorted(self.by_term, key=len, reverse=True)
        self._re = (
            re.compile(rf"(?<![{_BN}])(?:" + "|".join(re.escape(t) for t in terms) + rf")(?![{_BN}])")
            if terms
            else None
        )

    def __len__(self) -> int:
        return sum(len(v) for v in self.by_term.values())

    def match(self, text: str) -> list[GlossaryMatch]:
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
            entries.extend(json.loads(path.read_text(encoding="utf-8"))["entries"])
    return Glossary(entries)
