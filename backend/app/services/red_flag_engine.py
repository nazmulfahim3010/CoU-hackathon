"""Deterministic, rule-based red-flag engine. No LLM, no network, no learned weights.

Evaluated on the patient-confirmed text. Rules are data (data/safety_rules/rules.json).
Design choices that favour safety:
  * A term is "negated" only when an explicit negation word directly follows it (within 3 tokens).
    Any other co-occurrence of a negation word does NOT suppress the alert.
  * If the same rule matches both negated and affirmed mentions, the rule is triggered.
  * Absence of a mention is never treated as absence of the symptom.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from app.schemas.safety import RuleResult, SafetyResponse
from app.services.glossary_service import DATA_DIR, clean_text

NOTICE_EN = ("No alert does NOT mean the patient is safe. Alerts are keyword rules over what the patient said, "
             "not a clinical assessment. Kotha is not a diagnostic tool.")
NOTICE_BN = "কোনো সতর্কতা না থাকার অর্থ এই নয় যে রোগী নিরাপদ। এটি রোগীর কথার ওপর নির্ধারিত নিয়মভিত্তিক পরীক্ষা, চিকিৎসা মূল্যায়ন নয়।"

_NEG = {"না", "নাই", "নেই", "নয়", "নাহ", "হয়নি", "করেনি", "no", "not", "without", "denies"}
_CLAUSE_SPLIT = re.compile(r"[,;।.?!\n]")


@lru_cache
def load_rules() -> dict:
    return json.loads((DATA_DIR / "safety_rules" / "rules.json").read_text(encoding="utf-8"))


_GAP = r"(?:\s+[^\s,;।.?!]+){0,2}\s+"  # up to two filler words, e.g. "বুকে খুব ব্যথা"


def _find(text: str, term: str) -> list[tuple[int, int]]:
    """Match a term; spaces inside multi-word terms tolerate up to two filler words (over-alerting
    is preferred to a missed emergency)."""
    pattern = _GAP.join(re.escape(p) for p in term.lower().split())
    return [(m.start(), m.end()) for m in re.finditer(pattern, text.lower())]


def _is_negated(text: str, end: int) -> bool:
    """True only if a negation word follows the match within 3 tokens in the same clause."""
    tail = _CLAUSE_SPLIT.split(text[end:], maxsplit=1)[0]
    toks = re.findall(r"[ঀ-৿A-Za-z]+", tail)[:3]
    return any(t.lower() in _NEG for t in toks)


def _result(rule: dict, status: str, matched: list[str]) -> RuleResult:
    return RuleResult(
        rule_id=rule["rule_id"], status=status, alert_level=rule["alert_level"],
        name_en=rule["name_en"], name_bn=rule["name_bn"],
        explanation_en=rule["explanation_en"], explanation_bn=rule["explanation_bn"],
        recommended_action_en=rule["recommended_action_en"], recommended_action_bn=rule["recommended_action_bn"],
        required_information=rule["required_information"], matched_text=matched,
        clinically_reviewed=bool(load_rules().get("clinically_reviewed", False)),
    )


def _evaluate_rule(rule: dict, text: str) -> RuleResult:
    hits: list[tuple[str, bool]] = []  # (matched text, negated?)
    for term in rule["terms"]:
        for start, end in _find(text, term):
            hits.append((text[start:end], _is_negated(text, end)))
    unique = list(dict.fromkeys(t for t, _ in hits))
    # show the exact words matched; drop fragments contained in a longer match
    matched = [t for t in unique if not any(t != o and t in o for o in unique)]
    if not hits:
        return _result(rule, "not_triggered", [])
    affirmed = [t for t, neg in hits if not neg]

    if rule["kind"] == "co_occurrence":
        if not affirmed:
            return _result(rule, "negated", matched)
        strict = [c for c in rule.get("context_strict", []) if _find(text, c)]
        if strict:
            return _result(rule, "triggered", matched + strict)
        loose = [c for c in rule.get("context_loose", []) if _find(text, c)]
        if loose:
            return _result(rule, "needs_information", matched + loose)
        return _result(rule, "not_triggered", [])

    return _result(rule, "triggered" if affirmed else "negated", matched)


def evaluate(session_id: str, confirmed_text: str) -> SafetyResponse:
    text = clean_text(confirmed_text)
    cfg = load_rules()
    results = [_evaluate_rule(r, text) for r in cfg["rules"]]
    return SafetyResponse(
        session_id=session_id,
        triggered=[r for r in results if r.status == "triggered"],
        needs_information=[r for r in results if r.status == "needs_information"],
        negated=[r for r in results if r.status == "negated"],
        rules_evaluated=len(results),
        ruleset_version=cfg["ruleset_version"],
        engine="deterministic-keyword-rules (no LLM)",
        notice_en=NOTICE_EN,
        notice_bn=NOTICE_BN,
    )
