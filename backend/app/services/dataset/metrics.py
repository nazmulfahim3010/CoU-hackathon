"""Plain-Python evaluation metrics (no dependencies): edit distance, CER, WER, and text diffs."""
from __future__ import annotations

import re
import unicodedata
from typing import Sequence

_PUNCT = re.compile(r"[।,.;:?!\"'()\[\]{}\-‐‑–—]")


def prepare(text: str) -> str:
    """NFC, no zero-width characters, punctuation removed, single spaces. Scoring text only; never stored."""
    text = unicodedata.normalize("NFC", text or "").translate(dict.fromkeys([0x200B, 0x200C, 0x200D]))
    return re.sub(r"\s+", " ", _PUNCT.sub(" ", text)).strip()


def edit_distance(ref: Sequence, hyp: Sequence) -> int:
    """Levenshtein distance (insert/delete/substitute, each cost 1)."""
    if not ref:
        return len(hyp)
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    """Character error rate over prepared text (spaces included). Reference of length 0 gives 0.0 or 1.0."""
    ref, hyp = prepare(reference), prepare(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return edit_distance(ref, hyp) / len(ref)


def wer(reference: str, hypothesis: str) -> float:
    """Word error rate over prepared, whitespace-tokenised text."""
    ref, hyp = prepare(reference).split(), prepare(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return edit_distance(ref, hyp) / len(ref)


def exact_match(reference: str, hypothesis: str) -> bool:
    return prepare(reference) == prepare(hypothesis)
