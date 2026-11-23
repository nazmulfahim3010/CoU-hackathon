"""Structured clinical extraction from the patient-CONFIRMED transcript only."""
from __future__ import annotations

from pydantic import ValidationError

from app.config import Settings
from app.core.exceptions import KothaError
from app.core.logging import get_logger
from app.schemas.clinical import ClinicalExtraction
from app.services.dialect_normalizer import parse_json_object
from app.services.llm_provider import get_llm

log = get_logger("extractor")
MAX_ATTEMPTS = 3

SYSTEM = (
    "You extract structured intake information from a patient's confirmed statement (standard Bangla) "
    "for a clinician. You are NOT diagnosing.\n"
    "STRICT RULES:\n"
    "- Use ONLY what the patient said. Never invent details, never infer a diagnosis, never suggest treatment.\n"
    "- Each field has status: 'reported' (patient said it), 'uncertain' (patient was unsure or vague), "
    "or 'not_reported' (not mentioned). Missing information is 'not_reported' with bn/en null. "
    "NEVER treat 'not mentioned' as 'absent'.\n"
    "- negative_symptoms: ONLY symptoms the patient explicitly said they do NOT have.\n"
    "- uncertain_or_missing: things the clinician will need to ask or confirm.\n"
    "- model_noted_red_flag_indicators: serious-sounding symptoms mentioned (a hint only; a separate rule engine decides alerts).\n"
    "- Provide every text value in both Bangla (bn) and English (en).\n"
    "Respond ONLY with JSON of this exact shape:\n"
    '{"chief_complaint":{"status":"reported|uncertain|not_reported","bn":null,"en":null},'
    '"symptoms":[{"bn":"","en":""}],'
    '"duration":{"status":"","bn":null,"en":null},"severity":{"status":"","bn":null,"en":null},'
    '"relevant_history":{"status":"","bn":null,"en":null},"current_medications":{"status":"","bn":null,"en":null},'
    '"allergies":{"status":"","bn":null,"en":null},'
    '"associated_symptoms":[{"bn":"","en":""}],"negative_symptoms":[{"bn":"","en":""}],'
    '"uncertain_or_missing":[{"bn":"","en":""}],"model_noted_red_flag_indicators":[{"bn":"","en":""}]}'
)


async def extract(confirmed_text: str, settings: Settings) -> ClinicalExtraction:
    llm = get_llm(settings)
    user = f"Patient-confirmed statement:\n{confirmed_text}\n\nJSON:"
    last_error = "unknown"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        prompt = user if attempt == 1 else (
            f"{user}\n\nYour previous reply was invalid ({last_error}). "
            "Reply again with ONLY valid JSON in the exact shape required."
        )
        raw = await llm.complete(SYSTEM, prompt, max_tokens=2000)
        try:
            return ClinicalExtraction.model_validate(parse_json_object(raw))
        except (ValueError, ValidationError) as exc:
            last_error = type(exc).__name__
            log.warning("extraction_invalid attempt=%s error=%s", attempt, last_error)
    raise KothaError(
        502,
        "EXTRACTION_FAILED",
        "মডেলটি ক্লিনিক্যাল তথ্য সঠিকভাবে নিষ্কাশন করতে পারেনি (Clinical extraction failed). অনুগ্রহ করে আবার চেষ্টা করুন বা ডেমো মোড ব্যবহার করুন।",
    )
