"""Script classification and Romanized Bangla ('Banglish') transliteration service.

Deterministic table fallback + LLM transliteration.
Strict invariant: Transliterate Roman letters into Bengali script phonetically.
Never translate, never invent symptoms, preserve numbers and negation.
"""
from __future__ import annotations

import json
import re
from typing import Literal

from app.config import Settings
from app.core.logging import get_logger
from app.services.glossary_service import clean_text
from app.services.llm_provider import get_llm, llm_configured

log = get_logger("transliteration")

ScriptType = Literal["bangla_script", "romanized", "mixed"]

# Deterministic Roman-to-Bangla dictionary for common dialect/clinical words.
# Per non-negotiable rules: marked unverified unless independently verified.
DETERMINISTIC_ROMAN_TO_BANGLA: dict[str, str] = {
    # Pronouns & common terms
    "amar": "আমার",
    "amare": "আমারে",
    "amra": "আমরা",
    "amader": "আমাদের",
    "tar": "তার",
    "apnar": "আপনার",
    "rogi": "রোগী",
    # Negation words (STRICTLY PRESERVED)
    "na": "না",
    "nah": "নাহ",
    "nai": "নাই",
    "nay": "নায়",
    "nei": "নেই",
    "ni": "নি",
    "noy": "নয়",
    "noyto": "নয়তো",
    # Symptoms & Body parts (prompt specified common words)
    "pet": "পেট",
    "peto": "পেটো",
    "pete": "পেটে",
    "petot": "পেটে",
    "bedna": "বেদনা",
    "betha": "ব্যথা",
    "byatha": "ব্যথা",
    "bedon": "বেদনা",
    "jor": "জ্বর",
    "matha": "মাথা",
    "mathat": "মাথায়",
    "buk": "বুক",
    "buke": "বুকে",
    "buko": "বুকে",
    "bukut": "বুকে",
    "kashi": "কাশি",
    "kasi": "কাশি",
    "bomi": "বমি",
    "din": "দিন",
    "dino": "দিন",
    "shash": "শ্বাস",
    "shas": "শ্বাস",
    "shashkoshto": "শ্বাসকষ্ট",
    "rokto": "রক্ত",
    "khub": "খুব",
    "beshi": "বেশি" or "বেশী",
    "alpo": "অল্প",
    "dhore": "ধরে",
    "thaki": "থাকি",
    "hoise": "হয়েছে",
    "hoyeche": "হয়েছে",
    "ache": "আছে",
    "ase": "আছে",
    # Verbs
    "kor": "কর",
    "korer": "করের",
    "kore": "করে",
    "korche": "করছে",
    "korsi": "করছি",
    "korsina": "করছিনা",
    "kori": "করি",
    "lagse": "লাগছে",
    "lagsena": "লাগছেনা",
    # Numbers (words)
    "ek": "এক",
    "dui": "দুই",
    "tin": "তিন",
    "char": "চার",
    "pach": "পাঁচ",
    "choy": "ছয়",
    "shat": "সাত",
    "aat": "আট",
    "noy_num": "নয়",
    "dosh": "দশ",
}

TRANSLITERATION_WARNING = (
    "Roman letters detected and converted to Bangla script, please check carefully "
    "(রোমান হরফে লেখা শনাক্ত হয়েছে এবং বাংলা লিপিতে রূপান্তর করা হয়েছে, অনুগ্রহ করে সতর্কতার সাথে মিলিয়ে নিন)।"
)

UNVERIFIED_TABLE_WARNING = (
    "LLM transliteration unavailable; deterministic table fallback used with unverified entries. Please review carefully."
)


def classify_script(text: str) -> ScriptType:
    """Classify text as 'bangla_script', 'romanized', or 'mixed'.

    Uses Unicode ranges:
    Bengali: \u0980-\u09FF
    Latin: A-Za-z
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return "bangla_script"

    letters = [ch for ch in cleaned if ch.isalpha()]
    if not letters:
        has_bangla = any("\u0980" <= ch <= "\u09ff" for ch in cleaned)
        return "bangla_script" if has_bangla else "romanized"

    bangla_count = sum(1 for ch in letters if "\u0980" <= ch <= "\u09ff")
    latin_count = sum(1 for ch in letters if ("a" <= ch <= "z") or ("A" <= ch <= "Z"))
    total = len(letters)

    if bangla_count > 0 and latin_count == 0:
        return "bangla_script"
    if latin_count > 0 and bangla_count == 0:
        return "romanized"

    # Both scripts are present
    if bangla_count / total >= 0.85:
        return "bangla_script"
    if latin_count / total >= 0.85:
        return "romanized"
    return "mixed"


def deterministic_transliterate(text: str) -> str:
    """Transliterate Romanized words using the deterministic word table.

    Preserves already-Bangla tokens, digits, and punctuation.
    Entries in DETERMINISTIC_ROMAN_TO_BANGLA are marked unverified.
    """
    # Tokenize preserving delimiters/whitespace
    tokens = re.split(r"(\s+|[^\w\s])", text)
    out_tokens: list[str] = []
    for token in tokens:
        clean_tok = token.strip().lower()
        if clean_tok in DETERMINISTIC_ROMAN_TO_BANGLA:
            out_tokens.append(DETERMINISTIC_ROMAN_TO_BANGLA[clean_tok])
        else:
            out_tokens.append(token)
    return clean_text("".join(out_tokens))


LLM_TRANSLITERATION_SYSTEM_PROMPT = (
    "You are a strict phonetic transliteration engine that converts Romanized Bangla ('Banglish') "
    "into Bengali script (বাংলা লিপি).\n"
    "STRICT SAFETY & FIDELITY RULES:\n"
    "1. Only transliterate Roman letters into Bengali script phonetically. DO NOT translate into English.\n"
    "2. DO NOT normalize or change regional dialect words into standard Bangla; keep the dialect phonetics "
    "(e.g. 'peto' -> 'পেটো', 'bedna' -> 'বেদনা', 'korer' -> 'করের', 'buke' -> 'বুকে', 'jor' -> 'জ্বর', 'mathat' -> 'মাথায়').\n"
    "3. Keep all numbers (1, 2, 3... or এক, দুই...) and negation words exactly preserved "
    "('na' -> 'না', 'nai' -> 'নাই', 'nei' -> 'নেই', 'ni' -> 'নি', 'noy' -> 'নয়').\n"
    "4. Do NOT add, invent, or drop any symptoms or words.\n"
    "Respond ONLY with a valid JSON object in this exact schema:\n"
    "{\n"
    '  "transliterated_text": "<Bengali script sentence>"\n'
    "}"
)


async def transliterate_roman_to_bangla(
    text: str, settings: Settings, use_llm: bool = True
) -> tuple[str, list[str]]:
    """Transliterate Romanized/mixed input into Bengali script.

    Returns: (transliterated_text, warnings)
    Strictly avoids inventing text or translating into English.
    """
    text = clean_text(text)
    warnings: list[str] = [TRANSLITERATION_WARNING]

    if use_llm and llm_configured(settings):
        llm = get_llm(settings)
        user_prompt = (
            f"Input Romanized text: {text}\n"
            f"Output JSON with transliterated_text in Bengali script:"
        )
        try:
            raw_reply = await llm.complete(LLM_TRANSLITERATION_SYSTEM_PROMPT, user_prompt)
            # Parse JSON
            raw = re.sub(r"^```(?:json)?|```$", "", raw_reply.strip(), flags=re.MULTILINE).strip()
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(raw[start : end + 1])
                candidate = (data.get("transliterated_text") or "").strip()
                # Verify that candidate is predominantly Bengali script
                if candidate and classify_script(candidate) == "bangla_script":
                    return candidate, warnings
                log.warning("llm_transliteration_insufficient_bangla candidate=%s", candidate[:50])
        except Exception as exc:
            log.warning("llm_transliteration_failed error=%s", type(exc).__name__)

    # Fallback to deterministic word table
    fallback = deterministic_transliterate(text)
    warnings.append(UNVERIFIED_TABLE_WARNING)
    return fallback, warnings
