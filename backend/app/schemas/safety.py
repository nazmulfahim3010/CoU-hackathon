from typing import Literal

from pydantic import BaseModel

RuleStatus = Literal["triggered", "needs_information", "not_triggered", "negated"]
AlertLevel = Literal["emergency", "urgent", "info"]


class RuleResult(BaseModel):
    rule_id: str
    status: RuleStatus
    alert_level: AlertLevel
    name_en: str
    name_bn: str
    explanation_en: str
    explanation_bn: str
    recommended_action_en: str
    recommended_action_bn: str
    required_information: list[str]
    matched_text: list[str]
    clinically_reviewed: bool


class SafetyRequest(BaseModel):
    session_id: str


class SafetyResponse(BaseModel):
    session_id: str
    triggered: list[RuleResult]
    needs_information: list[RuleResult]
    negated: list[RuleResult]
    rules_evaluated: int
    ruleset_version: str
    engine: str
    notice_en: str
    notice_bn: str
