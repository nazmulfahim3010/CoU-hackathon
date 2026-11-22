"""Dialect normalization: glossary matching + LLM, with meaning-preservation guards."""
from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.config import Settings
from app.core.logging import get_logger
from app.schemas.normalization import GlossaryMatch, LLMNormalization, NormalizationResponse
from app.services.glossary_service import Glossary, clean_text, load_glossary
from app.services.providers.llm import get_llm

log = get_logger("normalizer")

DISCLAIMER = (
    "Normalization is AI/glossary-assisted and may be wrong, especially for regional dialects. "
    "The patient or helper must review it."
)

_NEG_WORDS = {"না", "নাই", "নেই", "নয়", "নি", "নাহ"}
_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_NUM_WORDS = ["এক", "দুই", "তিন", "চার", "পাঁচ", "ছয়", "সাত", "আট", "দশ", "আধা"]
_UNIT_STEMS = ["ঘণ্টা", "ঘন্টা", "দিন", "সপ্তাহ", "মাস", "বছর", "রাত"]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[ঀ-৿A-Za-z0-9]+", text)


def count_negations(text: str) -> int:
    n = 0
    for t in _tokens(text):
        if t in _NEG_WORDS or (len(t) >= 4 and t.endswith("নি")):
            n += 1
    return n


def check_meaning_preservation(original: str, normalized: str) -> list[str]:
    """Return a list of problems; an empty list means the guards passed."""
    problems: list[str] = []
    if count_negations(original) != count_negations(normalized):
        problems.append("negation_changed")
    o, n = original.translate(_DIGITS), normalized.translate(_DIGITS)
    if set(re.findall(r"\d+", o)) - set(re.findall(r"\d+", n)):
        problems.append("number_lost")
    ot, nt = _tokens(original), _tokens(normalized)
    if any(w in ot and w not in nt for w in _NUM_WORDS) and "number_lost" not in problems:
        problems.append("number_lost")
    if any(u in original and u not in normalized for u in _UNIT_STEMS):
        problems.append("duration_unit_lost")
    return problems


SYSTEM = (
    "You normalize a Bangladeshi patient's regional-dialect Bangla into standard Bangla for a clinical intake.\n"
    "STRICT RULES:\n"
    "- Preserve the exact meaning. Never add, invent or remove symptoms, durations, severities, medicines or body parts.\n"
    "- Keep negation exactly (না/নেই/নাই/নি must remain negations). Do not turn uncertain statements into certain ones.\n"
    "- Keep numbers and time expressions unchanged in meaning.\n"
    "- Use the glossary hints when they fit the context; they are unverified drafts and may not fit.\n"
    "- If a word is unclear, keep it as written and list it in uncertain_spans.\n"
    "- Do not diagnose, explain, or add advice.\n"
    'Respond ONLY with JSON: {"normalized": "<standard Bangla>", "uncertain_spans": ["<original words you were unsure about>"]}'
)

FEW_SHOT = (
    "Illustrative format examples (not clinical data):\n"
    "Input: আইজ দুই দিন ধরি পেটে বিষ, বমি নাই\n"
    'Output: {"normalized": "আজ দুই দিন ধরে পেটে ব্যথা, বমি নেই", "uncertain_spans": []}\n'
    "Input: মোর গাও গরম আছিল কিনা বুঝি নাই\n"
    'Output: {"normalized": "আমার শরীর গরম ছিল কিনা বুঝিনি", "uncertain_spans": []}'
)


def parse_json_object(raw: str) -> dict:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object")
    return json.loads(raw[start : end + 1])


async def normalize(
    original: str, settings: Settings, use_llm: bool, glossary: Glossary | None = None
) -> NormalizationResponse:
    glossary = glossary or load_glossary()
    text = clean_text(original)
    matches: list[GlossaryMatch] = glossary.match(text)
    glossary_only = Glossary.apply(text, matches)
    warnings: list[str] = []
    uncertain: list[str] = [m.regional for m in matches if m.verification != "verified"]
    normalized, source, provider = glossary_only, "glossary_only", "glossary"

    if use_llm:
        llm = get_llm(settings)  # raises 503 if not configured
        hints = (
            "\n".join(f"- {m.regional} → {m.standard} ({m.english}) [{m.dialect}, {m.verification}]" for m in matches)
            or "(none)"
        )
        user = f"{FEW_SHOT}\n\nGlossary hints for this input:\n{hints}\n\nInput: {text}\nOutput:"
        try:
            parsed = LLMNormalization.model_validate(parse_json_object(await llm.complete(SYSTEM, user)))
            problems = check_meaning_preservation(text, parsed.normalized)
            if problems:
                warnings.append(
                    f"LLM output failed meaning-preservation checks ({', '.join(problems)}); "
                    "glossary-only result shown instead."
                )
                log.warning("llm_normalization_rejected problems=%s", problems)
            else:
                normalized, source, provider = clean_text(parsed.normalized), "llm_with_glossary", llm.name
                uncertain = list(dict.fromkeys(uncertain + parsed.uncertain_spans))
        except (ValueError, ValidationError):
            warnings.append("LLM returned an invalid response; glossary-only result shown instead.")
            log.warning("llm_normalization_invalid")

    if not matches and source == "glossary_only":
        warnings.append("No glossary terms matched; text is unchanged. Please review carefully.")
    return NormalizationResponse(
        session_id="",
        original=text,
        normalized=normalized,
        source=source,
        glossary_matches=matches,
        uncertain_spans=uncertain,
        warnings=warnings,
        provider=provider,
        disclaimer=DISCLAIMER,
    )
