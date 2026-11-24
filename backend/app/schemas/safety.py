from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

RuleStatus = Literal["triggered", "explicitly_denied", "not_mentioned", "insufficient_information"]
AlertLevel = Literal["emergency", "urgent", "caution"]
ReviewStatus = Literal["pending_clinical_review", "reviewed"]


class TriggerConfig(BaseModel):
    terms_bn: list[str] = Field(default_factory=list)
    terms_en: list[str] = Field(default_factory=list)
    required_context: dict[str, Any] | None = None
    co_occurrence: dict[str, Any] | None = None


class SafetyRule(BaseModel):
    rule_id: str
    name_en: str
    name_bn: str
    trigger: TriggerConfig
    negation_window: int = 3
    alert_level: AlertLevel
    explanation_bn: str
    explanation_en: str
    recommended_action_bn: str
    recommended_action_en: str
    review_status: ReviewStatus = "pending_clinical_review"
    reviewed_against: str | None = None
    aliases: list[str] = Field(default_factory=list)


class SafetyRulesetConfig(BaseModel):
    ruleset_version: str
    clinically_reviewed: bool = False
    review_note: str
    rules: list[SafetyRule]


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
    matched_text: list[str] = Field(default_factory=list)
    matched_span: str | None = None
    required_information: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = "pending_clinical_review"
    reviewed_against: str | None = None
    clinically_reviewed: bool = False
    aliases: list[str] = Field(default_factory=list)


class SafetyRequest(BaseModel):
    session_id: str
    age_group: str | None = None


class SafetyResponse(BaseModel):
    session_id: str
    triggered: list[RuleResult] = Field(default_factory=list)
    explicitly_denied: list[RuleResult] = Field(default_factory=list)
    insufficient_information: list[RuleResult] = Field(default_factory=list)
    not_mentioned: list[RuleResult] = Field(default_factory=list)
    
    # Backward compatibility lists (populated from explicitly_denied and insufficient_information)
    negated: list[RuleResult] = Field(default_factory=list)
    needs_information: list[RuleResult] = Field(default_factory=list)
    
    rules_evaluated: int
    ruleset_version: str
    engine: str = "deterministic-keyword-rules (no LLM)"
    notice_en: str
    notice_bn: str
    warnings: list[str] = Field(default_factory=list)
    mode: str = "live"
