"""Structured clinical extraction from the patient-CONFIRMED transcript only.

The LLM proposes a structure; deterministic grounding (services/grounding.py) then checks every claim against
the patient's own words. Ungrounded claims trigger a corrective retry and, if they persist, are removed and
recorded for the clinician. They are never kept.
"""
from __future__ import annotations

from pydantic import ValidationError

from app.config import Settings
from app.core.exceptions import KothaError
from app.core.logging import get_logger
from app.schemas.clinical import ClinicalExtraction
from app.services.dialect_normalizer import parse_json_object
from app.services.grounding import describe_problems, ground_extraction
from app.services.llm_provider import get_llm

log = get_logger("extractor")
MAX_ATTEMPTS = 3

SYSTEM = (
    "You extract structured intake information from a patient's confirmed statement (standard Bangla) "
    "for a clinician. You are NOT diagnosing.\n"
    "STRICT RULES:\n"
    "- Use ONLY what the patient said. Never invent details, never infer a diagnosis, never suggest treatment.\n"
    '- EVERY non-empty value needs an "evidence" field: an EXACT substring copied from the patient\'s statement '
    "(same spelling, no paraphrase). If you cannot quote it, do not output it.\n"
    "- Never name a symptom (pain location, vomiting, fever, cough, breathing, bleeding...) that the patient did "
    "not say, even if it seems likely or related to what they said.\n"
    "- Each field has status: 'reported' (patient said it), 'uncertain' (patient was unsure or vague), "
    "or 'not_reported' (not mentioned). Missing information is 'not_reported' with bn/en/evidence null. "
    "NEVER treat 'not mentioned' as 'absent'.\n"
    "- negative_symptoms: ONLY symptoms the patient explicitly said they do NOT have.\n"
    "- uncertain_or_missing: things the clinician will need to ask or confirm (evidence may be null here).\n"
    "- model_noted_red_flag_indicators: serious-sounding symptoms the patient mentioned (a hint only; "
    "a separate rule engine decides alerts).\n"
    "- Provide every text value in both Bangla (bn) and English (en).\n"
    "Respond ONLY with JSON of this exact shape:\n"
    '{"chief_complaint":{"status":"reported|uncertain|not_reported","bn":null,"en":null,"evidence":null},'
    '"symptoms":[{"bn":"","en":"","evidence":""}],'
    '"duration":{"status":"","bn":null,"en":null,"evidence":null},'
    '"severity":{"status":"","bn":null,"en":null,"evidence":null},'
    '"relevant_history":{"status":"","bn":null,"en":null,"evidence":null},'
    '"current_medications":{"status":"","bn":null,"en":null,"evidence":null},'
    '"allergies":{"status":"","bn":null,"en":null,"evidence":null},'
    '"associated_symptoms":[{"bn":"","en":"","evidence":""}],'
    '"negative_symptoms":[{"bn":"","en":"","evidence":""}],'
    '"uncertain_or_missing":[{"bn":"","en":""}],'
    '"model_noted_red_flag_indicators":[{"bn":"","en":"","evidence":""}]}'
)


async def extract(confirmed_text: str, settings: Settings) -> ClinicalExtraction:
    llm = get_llm(settings)
    user = f"Patient-confirmed statement:\n{confirmed_text}\n\nJSON:"
    feedback = ""
    result: ClinicalExtraction | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        raw = await llm.complete(SYSTEM, user + feedback, max_tokens=2000)
        try:
            parsed = ClinicalExtraction.model_validate(parse_json_object(raw))
        except (ValueError, ValidationError) as exc:
            feedback = (
                f"\n\nYour previous reply was invalid ({type(exc).__name__}). "
                "Reply again with ONLY valid JSON in the exact shape required."
            )
            log.warning("extraction_invalid attempt=%s error=%s", attempt, type(exc).__name__)
            continue
        grounded = ground_extraction(parsed, confirmed_text)
        problems = describe_problems(parsed, grounded)
        result = grounded
        if not problems:
            return grounded
        log.warning("extraction_ungrounded attempt=%s count=%s", attempt, len(problems))
        feedback = (
            "\n\nYour previous reply contained claims that are NOT in the patient's statement: "
            + "; ".join(problems[:6])
            + ". Output only claims whose evidence is an exact quote from the statement."
        )
    if result is not None:
        return result  # grounded: unsupported claims were removed and recorded for the clinician
    raise KothaError(
        502,
        "EXTRACTION_FAILED",
        "মডেলটি ক্লিনিক্যাল তথ্য সঠিকভাবে নিষ্কাশন করতে পারেনি (Clinical extraction failed). "
        "অনুগ্রহ করে আবার চেষ্টা করুন বা ডেমো মোড ব্যবহার করুন।",
    )
