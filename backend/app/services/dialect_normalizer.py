"""Dialect normalization: glossary matching + LLM, with deterministic meaning-preservation guards."""
from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import ValidationError

from app.config import Settings
from app.core.logging import get_logger
from app.schemas.normalization import (
    GlossaryMatch,
    LLMNormalization,
    NormalizationChange,
    NormalizationResponse,
    UncertainSegment,
)
from app.services.glossary_service import Glossary, clean_text, load_glossary
from app.services.llm_provider import get_llm

log = get_logger("normalizer")

DISCLAIMER = (
    "Normalization is AI/glossary-assisted and may be wrong, especially for regional dialects. "
    "The patient or helper must review it."
)

_NEG_WORDS = {"না", "নাই", "নেই", "নয়", "নি", "নাহ"}
_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_NUM_WORDS = ["এক", "দুই", "তিন", "চার", "পাঁচ", "ছয়", "সাত", "আট", "নয়", "দশ", "আধা", "দেড়", "আড়াই"]
_UNIT_STEMS = ["ঘণ্টা", "ঘন্টা", "দিন", "সপ্তাহ", "মাস", "বছর", "রাত"]

# Standard-Bangla clinical symptom phrases used for invented-symptom detection. A symptom phrase
# appearing in the normalized text but not in the original is accepted only when a glossary entry
# in the original maps to it. The set is extended from the glossary (symptom / pain / fever rows).
_KNOWN_SYMPTOMS = {
    "বমি",
    "শ্বাসকষ্ট",
    "কাশি",
    "ডায়রিয়া",
    "খিঁচুনি",
    "অজ্ঞান",
    "রক্ত",
    "বুকে ব্যথা",
    "পেটে ব্যথা",
    "পেট ব্যথা",
    "মাথা ব্যথা",
    "মাথাব্যথা",
}
_SYMPTOM_CATEGORIES = {"symptom", "pain_description", "fever"}

# Negation words in standard Bangla. Dialect-specific forms (e.g. Sylheti "নায়", "করসিনা",
# "খাইসিনা") are learned from the verified glossary by `negation_forms`.
_NEG_SUFFIXES = ("না", "নায়", "নাই", "নেই")


def _tokens(text: str) -> list[str]:
    return re.findall(r"[ঀ-৿A-Za-z0-9]+", text)


def negation_forms(glossary: Glossary | None) -> frozenset[str]:
    """Dialect negation tokens learned from glossary entries whose standard form is a negation.

    Only regional tokens of entries whose *standard* text contains a base negation are considered,
    and a token must itself look like a negation (ends in না/নায়/নাই/নেই), so ordinary words are
    never treated as negations.
    """
    if glossary is None:
        return frozenset()
    cached = getattr(glossary, "_neg_forms_cache", None)
    if cached is not None:
        return cached
    forms: set[str] = set()
    for entry in glossary.entries:
        if not any(_is_base_negation(t) for t in _tokens(entry.standard_bangla)):
            continue
        for t in _tokens(entry.regional_expression):
            if t.endswith(_NEG_SUFFIXES):
                forms.add(t)
    result = frozenset(forms)
    glossary._neg_forms_cache = result  # type: ignore[attr-defined]
    return result


def _is_base_negation(token: str) -> bool:
    return token in _NEG_WORDS or (len(token) >= 4 and token.endswith("নি"))


def count_negations(text: str, extra_forms: frozenset[str] | set[str] = frozenset()) -> int:
    """Count explicit and inflectional negation markers (plus dialect forms, when given)."""
    return sum(1 for t in _tokens(text) if _is_base_negation(t) or t in extra_forms)


_NUM_WORD_VALUES = {"এক": 1, "দুই": 2, "তিন": 3, "চার": 4, "পাঁচ": 5, "ছয়": 6, "সাত": 7, "আট": 8, "দশ": 10}


def _numbers(text: str) -> set[int]:
    """Numeric values mentioned as digits (০-৯ or 0-9) or as the number words above."""
    values = {int(x) for x in re.findall(r"\d+", text.translate(_DIGITS))}
    values.update(_NUM_WORD_VALUES[t] for t in _tokens(text) if t in _NUM_WORD_VALUES)
    return values


def _remove_spans(text: str, spans: list[str]) -> str:
    for sp in spans:
        text = text.replace(sp, " ")
    return text


def check_meaning_preservation(original: str, normalized: str, glossary: Glossary | None = None) -> list[str]:
    """Return a list of problems; an empty list means the deterministic guards passed.

    The guards are glossary-aware: a verified glossary mapping is an allowed transformation, but
    anything outside the glossary must preserve negation, numbers, duration units and symptoms.
    """
    glossary = glossary or load_glossary()
    forms = negation_forms(glossary)
    matches = glossary.match(original)
    problems: list[str] = []

    # 1. Negation. A glossary phrase may legitimately turn a negated dialect phrase into a clinical
    #    phrase without "না" (e.g. "ঠিক করি মাততে পারে না" -> "কথা জড়িয়ে যাচ্ছে"), so the normalized count
    #    may be lower by exactly that much (and higher only where the glossary adds a negation).
    orig_neg = count_negations(original, forms)
    norm_neg = count_negations(normalized, forms)
    drop = sum(max(0, count_negations(m.regional, forms) - count_negations(m.standard, forms)) for m in matches)
    add = sum(max(0, count_negations(m.standard, forms) - count_negations(m.regional, forms)) for m in matches)
    if not (orig_neg - drop <= norm_neg <= orig_neg + add):
        problems.append("negation_changed")

    # 2-3. Number preservation by VALUE, so "৩ দিন" -> "তিন দিন" is fine but "তিন দিন" -> "দিন" is not.
    #      Number words inside a glossary span that deliberately drops them are excused.
    def _excused(stem: str, *, token: bool) -> str:
        spans = [
            m.regional
            for m in matches
            if (stem in _tokens(m.regional) if token else stem in m.regional)
            and not (stem in _tokens(m.standard) if token else stem in m.standard)
        ]
        return _remove_spans(original, spans)

    excused_spans = [
        m.regional
        for m in matches
        for w in _NUM_WORD_VALUES
        if w in _tokens(m.regional) and w not in _tokens(m.standard)
    ]
    orig_for_numbers = _remove_spans(original, excused_spans)
    if _numbers(orig_for_numbers) - _numbers(normalized):
        problems.append("number_lost")

    # 4. Duration unit preservation
    if any(u in _excused(u, token=False) and u not in normalized for u in _UNIT_STEMS):
        problems.append("duration_unit_lost")

    # 5. Invented symptom guard
    symptoms = set(_KNOWN_SYMPTOMS)
    symptoms.update(
        e.standard_bangla for e in glossary.entries if e.category in _SYMPTOM_CATEGORIES and len(e.standard_bangla) >= 3
    )
    for sym in symptoms:
        if sym in normalized and sym not in original and not any(sym in m.standard for m in matches):
            problems.append("invented_symptom")
            break

    return problems


def _load_few_shot_examples() -> str:
    """Build a Sylheti few-shot example from the first prepared demo sample.

    The input sentence is a verified-glossary example; the standard-Bangla output is a prepared rendering
    (not independently verified), and the `changes` list is computed from real glossary matches.
    """
    transcripts_path = Path(__file__).resolve().parent.parent.parent.parent / "demo_assets" / "transcripts.json"
    try:
        first = json.loads(transcripts_path.read_text(encoding="utf-8"))[0]
        orig = first["original_transcript"]
        std = first["standard_bangla"]
        changes = [
            {"original": m.regional, "normalized": m.standard, "reason": f"Verified glossary match ({m.category})", "source": "glossary"}
            for m in load_glossary().match(orig)
        ]
        example = {"normalized_text": std, "changes": changes, "uncertain_segments": []}
        return (
            "Sylheti few-shot example (input sentence from the verified glossary; standard rendering is a prepared sample):\n"
            f"Input: {orig}\n"
            f"Output: {json.dumps(example, ensure_ascii=False)}"
        )
    except (OSError, ValueError, KeyError, IndexError) as e:
        log.warning("few-shot example unavailable: %s", type(e).__name__)
        return "Few-shot example unavailable; follow the safety rules strictly."


SYSTEM_PROMPT = (
    "You normalize a Bangladeshi patient's regional dialect Bangla into standard Bangla for a clinical intake.\n"
    "STRICT SAFETY RULES:\n"
    "1. Never add or invent symptoms not explicitly stated in the input.\n"
    "2. Never drop medical details, numbers, durations, or severity descriptors.\n"
    "3. Keep negation exactly preserved (না/নেই/নাই/নি must stay negated). Never turn uncertain statements into certain ones.\n"
    "4. Keep uncertainty words unchanged ('মনে হয়', 'হয়তো', 'কিনা', 'বুঝি নাই').\n"
    "5. Do NOT diagnose, offer advice, or explain medical causes.\n"
    "6. Use glossary hints where appropriate.\n"
    "Respond ONLY with valid JSON in this exact shape:\n"
    '{\n'
    '  "normalized_text": "<standard Bangla sentence>",\n'
    '  "changes": [\n'
    '    {"original": "<dialect phrase>", "normalized": "<standard phrase>", "reason": "<brief rationale>", "source": "glossary"|"llm"}\n'
    '  ],\n'
    '  "uncertain_segments": [\n'
    '    {"text": "<unclear phrase>", "reason": "<why unclear>"}\n'
    '  ]\n'
    '}'
)


def parse_json_object(raw: str) -> dict:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in LLM output")
    return json.loads(raw[start : end + 1])


def parse_llm_response(raw: str) -> LLMNormalization:
    parsed_dict = parse_json_object(raw)
    norm = LLMNormalization.model_validate(parsed_dict)
    # Ensure final text exists
    if not norm.final_normalized:
        raise ValueError("LLM JSON missing normalized text")
    return norm


async def normalize(
    original: str, settings: Settings, use_llm: bool, glossary: Glossary | None = None
) -> NormalizationResponse:
    glossary = glossary or load_glossary()
    text = clean_text(original)
    matches: list[GlossaryMatch] = glossary.match(text)
    glossary_only = Glossary.apply(text, matches)
    warnings: list[str] = []
    uncertain_segments: list[UncertainSegment] = [
        UncertainSegment(text=m.regional, reason=f"Unverified dialect term ({m.dialect})")
        for m in matches
        if m.verification != "verified"
    ]
    uncertain_spans: list[str] = [m.regional for m in matches if m.verification != "verified"]
    changes: list[NormalizationChange] = [
        NormalizationChange(
            original=m.regional,
            normalized=m.standard,
            reason=f"Glossary match ({m.category})",
            source="glossary",
        )
        for m in matches
    ]

    normalized, source, provider = glossary_only, "glossary_only", "glossary"

    if use_llm:
        llm = get_llm(settings)
        few_shot = _load_few_shot_examples()
        hints = (
            "\n".join(f"- {m.regional} → {m.standard} ({m.english}) [{m.dialect}, {m.verification}]" for m in matches)
            or "(none)"
        )
        user_prompt = f"{few_shot}\n\nGlossary hints for this input:\n{hints}\n\nInput: {text}\nOutput:"

        try:
            raw_reply = await llm.complete(SYSTEM_PROMPT, user_prompt)
            parsed = parse_llm_response(raw_reply)
            problems = check_meaning_preservation(text, parsed.final_normalized, glossary)

            # If check fails, retry ONCE with targeted feedback
            if problems:
                log.warning("llm_normalization_guard_failed problems=%s, retrying once", problems)
                retry_user = (
                    f"{user_prompt}\n\n"
                    f"CRITICAL CORRECTION REQUIRED: Your previous output failed safety checks: {', '.join(problems)}.\n"
                    f"Please regenerate the JSON strictly preserving all original numbers, durations, and negations without inventing symptoms."
                )
                raw_retry = await llm.complete(SYSTEM_PROMPT, retry_user)
                retry_parsed = parse_llm_response(raw_retry)
                retry_problems = check_meaning_preservation(text, retry_parsed.final_normalized, glossary)

                if not retry_problems:
                    parsed = retry_parsed
                    problems = []
                else:
                    problems = retry_problems

            if problems:
                warnings.append(
                    f"LLM output failed meaning-preservation checks ({', '.join(problems)}); "
                    "glossary-only result shown instead."
                )
                log.warning("llm_normalization_rejected problems=%s", problems)
            else:
                normalized = clean_text(parsed.final_normalized)
                source = "llm_with_glossary"
                provider = llm.name
                if parsed.changes:
                    changes = parsed.changes
                if parsed.uncertain_segments:
                    uncertain_segments.extend(parsed.uncertain_segments)
                uncertain_spans = list(dict.fromkeys(uncertain_spans + parsed.uncertain_spans + [s.text for s in parsed.uncertain_segments]))
        except (ValueError, ValidationError) as exc:
            warnings.append("LLM returned an invalid response; glossary-only result shown instead.")
            log.warning("llm_normalization_invalid error=%s", exc)

    if not matches and source == "glossary_only":
        warnings.append("No glossary terms matched; text is unchanged. Please review carefully.")

    return NormalizationResponse(
        session_id="",
        original=text,
        normalized=normalized,
        source=source,
        glossary_matches=matches,
        changes=changes,
        uncertain_segments=uncertain_segments,
        uncertain_spans=uncertain_spans,
        warnings=warnings,
        provider=provider,
        mode="live",
        disclaimer=DISCLAIMER,
    )
