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

# Canonical clinical symptoms used for invented symptom detection
_KNOWN_SYMPTOMS = {
    "বমি",
    "শ্বাসকষ্ট",
    "কাশি",
    "ডায়রিয়া",
    "খিঁচুনি",
    "অজ্ঞান",
    "রক্ত",
    "বুকে ব্যথা",
    "বুগত ব্যতা",
    "পেটে ব্যথা",
    "ফেডে ব্যতা",
    "মাথা ব্যথা",
    "মাতাত ব্যতা",
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[ঀ-৿A-Za-z0-9]+", text)


def count_negations(text: str) -> int:
    """Count explicit and inflectional negation markers."""
    n = 0
    for t in _tokens(text):
        if t in _NEG_WORDS or (len(t) >= 4 and t.endswith("নি")):
            n += 1
    return n


def check_meaning_preservation(original: str, normalized: str, glossary: Glossary | None = None) -> list[str]:
    """Return a list of problems; an empty list means deterministic guards passed."""
    problems: list[str] = []

    # 1. Negation check
    if count_negations(original) != count_negations(normalized):
        problems.append("negation_changed")

    # 2. Number / digit preservation
    o_digits = set(re.findall(r"\d+", original.translate(_DIGITS)))
    n_digits = set(re.findall(r"\d+", normalized.translate(_DIGITS)))
    if o_digits - n_digits:
        problems.append("number_lost")

    # 3. Number words preservation
    ot, nt = _tokens(original), _tokens(normalized)
    if any(w in ot and w not in nt for w in _NUM_WORDS) and "number_lost" not in problems:
        problems.append("number_lost")

    # 4. Duration unit preservation
    if any(u in original and u not in normalized for u in _UNIT_STEMS):
        problems.append("duration_unit_lost")

    # 5. Invented symptom guard (ensure no unmentioned symptom appeared)
    for sym in _KNOWN_SYMPTOMS:
        if sym in normalized and sym not in original:
            # Check if it was introduced via a valid glossary translation
            is_glossary_translated = False
            if glossary:
                for match in glossary.match(original):
                    if sym in match.standard:
                        is_glossary_translated = True
                        break
            if not is_glossary_translated:
                problems.append("invented_symptom")
                break

    return problems


def _load_few_shot_examples() -> str:
    """Build few-shot examples taken strictly from unverified demo sample pairs in demo_assets/transcripts.json."""
    transcripts_path = Path(__file__).resolve().parent.parent.parent.parent / "demo_assets" / "transcripts.json"
    if transcripts_path.exists():
        try:
            data = json.loads(transcripts_path.read_text(encoding="utf-8"))
            if data and isinstance(data, list):
                first = data[0]
                orig = first.get("original_transcript", "")
                std = first.get("standard_bangla", "")
                return (
                    f"Sample few-shot example from demo transcripts (sample / unverified):\n"
                    f"Input: {orig}\n"
                    f'Output: {{"normalized_text": "{std}", "changes": [{{"original": "আইজ", "normalized": "আজ", "reason": "Standard time word", "source": "glossary"}}, {{"original": "ধরি", "normalized": "ধরে", "reason": "Standard postposition", "source": "glossary"}}, {{"original": "মাতাত ব্যতা", "normalized": "মাথায় ব্যথা", "reason": "Standard medical phrase", "source": "glossary"}}], "uncertain_segments": []}}'
                )
        except Exception as e:
            log.warning("failed to load demo transcripts: %s", e)

    return (
        'Sample few-shot example (sample / unverified):\n'
        'Input: আইজ তিন দিন ধরি মোর মাতাত ব্যতা, অল্প জ্বর আছে। হারাদিন ভাল লাগের না। প্যারাসিটামল একবার খাইছি।\n'
        'Output: {"normalized_text": "আজ তিন দিন ধরে আমার মাথায় ব্যথা, অল্প জ্বর আছে। সারাদিন ভালো লাগছে না। প্যারাসিটামল একবার খেয়েছি。", "changes": [{"original": "মাতাত ব্যতা", "normalized": "মাথায় ব্যথা", "reason": "Standard head pain phrase", "source": "glossary"}], "uncertain_segments": []}'
    )


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
