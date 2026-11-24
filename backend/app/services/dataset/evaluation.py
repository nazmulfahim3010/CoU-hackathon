"""Evaluation logic for the Sylheti corpus: ASR metrics, normalization semantic checks, rollups.

Pure functions (no network, no files) so they are unit-testable. ASR is scored against the ORIGINAL Sylheti
transcript; normalization is scored against the STANDARD Bangla reference. The two references are never mixed.
Automated checks are only a screen: anything flagged needs a human clinical-meaning review.
"""
from __future__ import annotations

from statistics import mean
from typing import Any, Iterable

from app.services.dataset.metrics import cer, exact_match, prepare, wer
from app.services.dialect_normalizer import _numbers, check_meaning_preservation, count_negations
from app.services.glossary_service import Glossary
from app.services.grounding import SYMPTOM_GROUPS, squash, symptoms_named_but_never_said

SEVERITY_WORDS = ("খুব", "অনেক", "প্রচণ্ড", "তীব্র", "হালকা", "অল্প", "বেশি", "মারাত্মক", "ভীষণ", "বাক্কা", "বহুত")
BODY_PART_STEMS = ("মাথা", "বুক", "পেট", "গলা", "পিঠ", "কোমর", "হাত", "পা ", "চোখ", "কান", "নাক", "দাঁত", "শরীর", "জিহ্বা", "ঘাড়")
WER_REVIEW_THRESHOLD = 0.6  # a normalization this far from the reference always needs a human look
MISMATCH_MARGIN = 0.2  # own-reference CER must beat the best other reference by this much to suspect a label swap


def asr_metrics(reference_original: str, hypothesis: str) -> dict[str, Any]:
    hyp_empty = not prepare(hypothesis)
    return {
        "cer": round(cer(reference_original, hypothesis), 4),
        "wer": round(wer(reference_original, hypothesis), 4),
        "exact_match": exact_match(reference_original, hypothesis),
        "empty_transcript": hyp_empty,
    }


def _groups(text: str) -> set[str]:
    sq = squash(text)
    return {g for g, variants in SYMPTOM_GROUPS.items() if any(squash(v) in sq for v in variants)}


def _present(text: str, words: Iterable[str]) -> set[str]:
    return {w.strip() for w in words if w in text}


def semantic_checks(original: str, normalized: str, reference: str, glossary: Glossary) -> dict[str, Any]:
    """Screen a normalization for meaning drift. `original` is the Sylheti text that was normalized."""
    problems = check_meaning_preservation(original, normalized, glossary)
    invented = symptoms_named_but_never_said(normalized, squash(original))
    ref_groups, out_groups = _groups(reference), _groups(normalized)
    missing, extra = sorted(ref_groups - out_groups), sorted(out_groups - ref_groups)
    ref_neg, out_neg = count_negations(reference), count_negations(normalized)
    ref_sev, out_sev = _present(reference, SEVERITY_WORDS), _present(normalized, SEVERITY_WORDS)
    ref_body, out_body = _present(reference, BODY_PART_STEMS), _present(normalized, BODY_PART_STEMS)
    w = wer(reference, normalized)
    flags = {
        "guard_problems": problems,  # negation_changed / number_lost / duration_unit_lost / invented_symptom
        "unsupported_symptom_groups": invented,  # named in the output, absent from the Sylheti original
        "negation_count_matches_reference": ref_neg == out_neg,
        "numbers_match_reference": _numbers(reference) == _numbers(normalized),
        "symptom_groups_missing_vs_reference": missing,
        "symptom_groups_extra_vs_reference": extra,
        "body_parts_missing_vs_reference": sorted(ref_body - out_body),
        "body_parts_extra_vs_reference": sorted(out_body - ref_body),
        "severity_marker_presence_matches": bool(ref_sev) == bool(out_sev),
    }
    review = bool(
        problems or invented or missing or extra or not flags["negation_count_matches_reference"]
        or not flags["numbers_match_reference"] or flags["body_parts_missing_vs_reference"]
        or flags["body_parts_extra_vs_reference"] or not flags["severity_marker_presence_matches"]
        or w > WER_REVIEW_THRESHOLD
    )
    return {
        "cer_vs_reference": round(cer(reference, normalized), 4),
        "wer_vs_reference": round(w, 4),
        "exact_match_reference": exact_match(reference, normalized),
        **flags,
        "requires_human_review": review,
    }


def possible_label_mismatches(transcripts: dict[str, str], references: dict[str, str]) -> list[dict[str, Any]]:
    """Diagnostic only: for each recording, is its recognised text much closer to ANOTHER row's reference?
    This is how a swapped audio/transcript pair would show up. The dataset itself is never altered."""
    out = []
    for rid, hyp in transcripts.items():
        if not prepare(hyp):
            continue
        scores = {other: cer(ref, hyp) for other, ref in references.items()}
        best = min(scores, key=scores.get)
        if best != rid and scores[rid] - scores[best] > MISMATCH_MARGIN:
            out.append({"recording_id": rid, "closer_to": best, "own_cer": round(scores[rid], 4), "other_cer": round(scores[best], 4)})
    return out


def _mean(values: list[float]) -> float | None:
    return round(mean(values), 4) if values else None


def asr_rollup(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in rows if r.get("status") == "ok"]
    scored = [r for r in ok if not r["asr"]["empty_transcript"]]
    n = len(rows)
    return {
        "recordings": n,
        "successful_transcriptions": len(ok),
        "failed_transcriptions": n - len(ok),
        "failure_rate": round((n - len(ok)) / n, 4) if n else None,
        "empty_transcripts": sum(1 for r in ok if r["asr"]["empty_transcript"]),
        "empty_transcript_rate": round(sum(1 for r in ok if r["asr"]["empty_transcript"]) / n, 4) if n else None,
        "exact_match_rate": round(sum(1 for r in ok if r["asr"]["exact_match"]) / n, 4) if n else None,
        "mean_cer": _mean([r["asr"]["cer"] for r in scored]),
        "mean_wer": _mean([r["asr"]["wer"] for r in scored]),
        "mean_processing_seconds": _mean([r["processing_seconds"] for r in ok]),
    }


def by_scenario(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault(r["scenario_card"], []).append(r)
    out = {}
    for card, items in sorted(groups.items()):
        roll = asr_rollup([i for i in items if "asr" in i or i.get("status") == "failed"])
        norm = [i["normalization_of_reference"] for i in items if "normalization_of_reference" in i]
        out[card] = {
            **roll,
            "normalization_needing_human_review": sum(1 for n in norm if n["requires_human_review"]),
            "normalization_checked": len(norm),
        }
    return out


def normalization_rollup(norm_rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(norm_rows)

    def count(pred) -> int:
        return sum(1 for r in norm_rows if pred(r))

    return {
        "pairs_evaluated": n,
        "mean_cer_vs_reference": _mean([r["cer_vs_reference"] for r in norm_rows]),
        "mean_wer_vs_reference": _mean([r["wer_vs_reference"] for r in norm_rows]),
        "exact_match_reference": count(lambda r: r["exact_match_reference"]),
        "negation_preserved_vs_reference": count(lambda r: r["negation_count_matches_reference"]),
        "negation_guard_failures": count(lambda r: "negation_changed" in r["guard_problems"]),
        "symptom_preserved": count(lambda r: not r["symptom_groups_missing_vs_reference"]),
        "body_part_preserved": count(lambda r: not r["body_parts_missing_vs_reference"]),
        "severity_marker_preserved": count(lambda r: r["severity_marker_presence_matches"]),
        "numbers_preserved": count(lambda r: r["numbers_match_reference"]),
        "duration_unit_guard_failures": count(lambda r: "duration_unit_lost" in r["guard_problems"]),
        "unsupported_symptom_insertions": count(lambda r: bool(r["unsupported_symptom_groups"])),
        "requires_human_review": count(lambda r: r["requires_human_review"]),
    }
