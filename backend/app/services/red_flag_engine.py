"""Deterministic, rule-based red-flag engine. No LLM, no network, no learned weights.

Evaluated on the patient-confirmed text and intake fields. Rules are loaded from
data/safety_rules/red_flags.json and validated by Pydantic schemas.

Safety invariants:
  * Purely deterministic keyword and co-occurrence rules. Absolutely no LLM is imported or called.
  * A term is "negated" only when an explicit negation word is detected within the rule's negation window
    (default 3 tokens) in the same clause, or directly preceding it (e.g. 'no chest pain').
  * Unrelated negations in separate clauses do NOT suppress alerts.
  * If a symptom is mentioned both affirmed and negated, affirmed beats negated (rule triggers).
  * Missing information is 'not_mentioned' (or 'insufficient_information'), never assumed 'absent'.
  * Infant fever requires infant context or intake age_group == 'infant'; ambiguous child fever
    yields 'insufficient_information'.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from app.schemas.safety import (
    RuleResult,
    SafetyResponse,
    SafetyRule,
    SafetyRulesetConfig,
)
from app.services.glossary_service import DATA_DIR, clean_text
from app.services.transliteration import classify_script

NOTICE_EN = "No alert does not mean the patient is safe. Clinician assessment is required."
NOTICE_BN = "কোনো সতর্কতা না থাকার অর্থ এই নয় যে রোগী নিরাপদ। চিকিৎসকের সরাসরি পর্যবেক্ষণ ও মূল্যায়ন আবশ্যক।"

_NEG_POST = {"না", "নাই", "নেই", "নয়", "নায়", "নাহ", "নি", "হয়নি", "করেনি", "no", "not", "without", "denies", "none"}
_NEG_PRE = {"no", "without", "denies", "না", "নেই", "নাই", "নায়"}
_CLAUSE_SPLIT = re.compile(r"[,;।.?!\n]")
_TOKEN_RE = re.compile(r"[ঀ-৿A-Za-z0-9]+")
_GAP = r"(?:\s+[^\s,;।.?!]+){0,2}\s+"  # tolerates up to 2 filler words (e.g. "বুকে খুব ব্যথা")


def _get_rules_path() -> Path:
    p = DATA_DIR / "safety_rules" / "red_flags.json"
    if p.exists():
        return p
    return DATA_DIR / "safety_rules" / "rules.json"


@lru_cache
def load_rules() -> dict:
    """Load and validate rules from JSON file using Pydantic SafetyRulesetConfig."""
    path = _get_rules_path()
    raw = json.loads(path.read_text(encoding="utf-8"))
    # Schema validation
    validated = SafetyRulesetConfig.model_validate(raw)
    return validated.model_dump()


def list_rules() -> list[SafetyRule]:
    cfg = load_rules()
    return [SafetyRule.model_validate(r) for r in cfg["rules"]]


def get_rules_info() -> dict:
    return load_rules()


def _normalize(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    # Hyphens/dashes become spaces so "হাত-পা অবশ" matches the rule term "হাত পা অবশ".
    text = re.sub(r"[-‐‑–—]", " ", text)
    return clean_text(text)


def _find(text: str, term: str) -> list[tuple[int, int]]:
    """Match a term with gap tolerance for compound terms."""
    if not text or not term:
        return []
    pattern = _GAP.join(re.escape(p) for p in term.lower().split())
    try:
        return [(m.start(), m.end()) for m in re.finditer(pattern, text.lower())]
    except re.error:
        return []


def _is_negated(text: str, start: int, end: int, window: int = 3) -> bool:
    """True if negation token occurs within `window` tokens in the same clause (after or immediately before)."""
    # 1. Post-negation within window in the same clause
    tail = _CLAUSE_SPLIT.split(text[end:], maxsplit=1)[0]
    toks_after = _TOKEN_RE.findall(tail)[:window]
    if any(t.lower() in _NEG_POST for t in toks_after):
        return True

    # 2. Pre-negation within 2 tokens before match in the same clause
    head_clauses = _CLAUSE_SPLIT.split(text[:start])
    head = head_clauses[-1] if head_clauses else ""
    toks_before = _TOKEN_RE.findall(head)[-2:]
    if any(t.lower() in _NEG_PRE for t in toks_before):
        return True

    return False


def _evaluate_rule(
    rule: dict,
    text: str,
    age_group: str | None = None,
    original_text: str = "",
) -> RuleResult:
    rule_id = rule["rule_id"]
    trigger = rule.get("trigger", {})
    terms_bn = trigger.get("terms_bn", [])
    terms_en = trigger.get("terms_en", [])
    all_terms = sorted(terms_bn + terms_en, key=len, reverse=True)
    window = rule.get("negation_window", 3)
    co_occur = trigger.get("co_occurrence") or {}
    aliases = rule.get("aliases", [])

    # Search in both confirmed text and original dialect text
    combined_text = f"{text}\n{original_text}".strip()

    hits: list[tuple[str, bool]] = []
    for term in all_terms:
        # Match against combined text
        for start, end in _find(combined_text, term):
            matched_snippet = combined_text[start:end]
            neg = _is_negated(combined_text, start, end, window=window)
            hits.append((matched_snippet, neg))

    # De-duplicate matched substrings (keep longest)
    unique_matches = list(dict.fromkeys(t for t, _ in hits))
    clean_matched = [t for t in unique_matches if not any(t != o and t in o for o in unique_matches)]

    has_mentions = len(hits) > 0
    affirmed_mentions = [t for t, neg in hits if not neg]
    is_affirmed = len(affirmed_mentions) > 0

    # Required information list based on rule
    req_info = []
    if rule_id == "CHEST_PAIN":
        req_info = ["Onset and duration", "Radiation to arm or jaw", "Associated breathlessness or sweating"]
    elif rule_id == "BREATHING_DIFFICULTY":
        req_info = ["Onset", "Whether at rest", "Lip or face colour change"]
    elif rule_id in ("HEAVY_BLEEDING", "PREGNANCY_BLEEDING"):
        req_info = ["Source of bleeding", "Amount and duration", "Estimated gestational age"]
    elif rule_id == "INFANT_FEVER":
        req_info = ["Age in days/weeks/months", "Measured temperature"]
    elif rule_id in ("UNCONSCIOUSNESS", "LOSS_OF_CONSCIOUSNESS"):
        req_info = ["Time of onset", "Duration of unresponsiveness", "Recovery status"]
    elif rule_id == "SEIZURE":
        req_info = ["Duration of seizure", "First episode or recurrent history"]
    elif rule_id == "SEVERE_DEHYDRATION":
        req_info = ["Urine output in last 12 hours", "Fluid intake ability", "Sunken fontanelle/eyes"]
    elif rule_id == "STROKE_SIGNS":
        req_info = ["Exact time symptoms started", "Side affected", "Speech impairment progression"]
    elif rule_id in ("BLOOD_IN_VOMIT_STOOL", "VOMITING_BLOOD"):
        req_info = ["Amount of blood", "Color (bright red vs dark coffee-ground)", "Associated dizziness"]

    # --- Rule specific evaluation logic ---

    # 1. INFANT_FEVER
    if rule_id == "INFANT_FEVER":
        if not has_mentions:
            return _build_result(rule, "not_mentioned", [], req_info, aliases)
        if not is_affirmed:
            return _build_result(rule, "explicitly_denied", clean_matched, req_info, aliases)

        # Check age_group and infant co-occurrence terms
        strict_markers = co_occur.get("context_strict", [
            "মাসের বাচ্চা", "মাসের শিশু", "দিনের বাচ্চা", "দিনের শিশু",
            "সপ্তাহের বাচ্চা", "সপ্তাহের শিশু", "নবজাতক", "infant", "newborn",
        ])
        loose_markers = co_occur.get("context_loose", [
            "বাচ্চা", "শিশু", "খোকা", "খুকি", "বাচ্চার", "শিশুর", "child", "baby",
        ])

        strict_matches = [m for m in strict_markers if _find(combined_text, m)]
        loose_matches = [m for m in loose_markers if _find(combined_text, m)]

        if age_group == "infant" or strict_matches:
            matched_context = list(dict.fromkeys(clean_matched + strict_matches))
            return _build_result(rule, "triggered", matched_context, req_info, aliases)
        elif loose_matches:
            if age_group in ("child", "adult", "older_adult"):
                return _build_result(rule, "not_mentioned", [], req_info, aliases)
            # Age not stated or ambiguous: report insufficient information
            matched_context = list(dict.fromkeys(clean_matched + loose_matches))
            return _build_result(rule, "insufficient_information", matched_context, req_info, aliases)
        else:
            # Fever in adult / general person without infant context
            return _build_result(rule, "not_mentioned", [], req_info, aliases)

    # 2. PREGNANCY_BLEEDING
    if rule_id == "PREGNANCY_BLEEDING":
        preg_terms = co_occur.get("pregnancy_terms", ["গর্ভবতী", "গর্ভাবস্থা", "গর্ভে", "প্রেগন্যান্ট", "পেটে বাচ্চা", "pregnant", "pregnancy"])
        bleed_terms = co_occur.get("bleeding_terms", ["রক্ত", "রক্তপাত", "রক্তক্ষরণ", "লাহু", "bleeding", "blood"])
        has_preg = any(_find(combined_text, pt) for pt in preg_terms)
        has_bleed_hits = [combined_text[s:e] for bt in bleed_terms for s, e in _find(combined_text, bt)]

        if has_mentions:
            if is_affirmed:
                return _build_result(rule, "triggered", clean_matched, req_info, aliases)
            return _build_result(rule, "explicitly_denied", clean_matched, req_info, aliases)

        if has_preg and has_bleed_hits:
            # Check if bleed is negated
            bleed_neg = all(_is_negated(combined_text, s, e, window=window) for bt in bleed_terms for s, e in _find(combined_text, bt))
            preg_match = [combined_text[s:e] for pt in preg_terms for s, e in _find(combined_text, pt)][:1]
            if bleed_neg:
                return _build_result(rule, "explicitly_denied", preg_match + has_bleed_hits[:1], req_info, aliases)
            return _build_result(rule, "triggered", preg_match + has_bleed_hits[:1], req_info, aliases)

        return _build_result(rule, "not_mentioned", [], req_info, aliases)

    # 3. Standard rules
    if not has_mentions:
        return _build_result(rule, "not_mentioned", [], req_info, aliases)

    if is_affirmed:
        return _build_result(rule, "triggered", clean_matched, req_info, aliases)

    return _build_result(rule, "explicitly_denied", clean_matched, req_info, aliases)


def _build_result(
    rule: dict,
    status: str,
    matched: list[str],
    req_info: list[str],
    aliases: list[str],
) -> RuleResult:
    matched_span = ", ".join(matched) if matched else None
    return RuleResult(
        rule_id=rule["rule_id"],
        status=status,
        alert_level=rule["alert_level"],
        name_en=rule["name_en"],
        name_bn=rule["name_bn"],
        explanation_en=rule["explanation_en"],
        explanation_bn=rule["explanation_bn"],
        recommended_action_en=rule["recommended_action_en"],
        recommended_action_bn=rule["recommended_action_bn"],
        required_information=req_info,
        matched_text=matched,
        matched_span=matched_span,
        review_status=rule.get("review_status", "pending_clinical_review"),
        reviewed_against=rule.get("reviewed_against"),
        clinically_reviewed=bool(rule.get("review_status") == "reviewed"),
        aliases=aliases,
    )


def evaluate(
    session_id: str,
    confirmed_text: str,
    age_group: str | None = None,
    original_transcript: str | None = None,
) -> SafetyResponse:
    """Evaluate deterministic red-flag rules against confirmed text and intake context.
    
    Zero LLM calls. Purely rule-based keyword matching with clause-bounded negation logic.
    """
    text = _normalize(confirmed_text)
    orig = _normalize(original_transcript or "")
    cfg = load_rules()
    rules = cfg.get("rules", [])

    results = [_evaluate_rule(r, text, age_group=age_group, original_text=orig) for r in rules]

    triggered = [r for r in results if r.status == "triggered"]
    explicitly_denied = [r for r in results if r.status == "explicitly_denied"]
    insufficient_info = [r for r in results if r.status == "insufficient_information"]
    not_mentioned = [r for r in results if r.status == "not_mentioned"]

    warnings: list[str] = []
    if classify_script(text) != "bangla_script":
        warnings.append("Text is not in Bangla script; red-flag check may be unreliable.")

    return SafetyResponse(
        session_id=session_id,
        triggered=triggered,
        explicitly_denied=explicitly_denied,
        insufficient_information=insufficient_info,
        not_mentioned=not_mentioned,
        negated=explicitly_denied,  # backward compatibility alias
        needs_information=insufficient_info,  # backward compatibility alias
        rules_evaluated=len(results),
        ruleset_version=cfg.get("ruleset_version", "1.0-draft"),
        engine="deterministic-keyword-rules (no LLM)",
        notice_en=NOTICE_EN,
        notice_bn=NOTICE_BN,
        warnings=warnings,
    )
