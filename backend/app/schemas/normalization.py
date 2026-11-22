from typing import Literal

from pydantic import BaseModel, Field


class GlossaryMatch(BaseModel):
    regional: str
    standard: str
    english: str
    dialect: str
    category: str
    verification: str
    start: int
    end: int


class NormalizationChange(BaseModel):
    original: str
    normalized: str
    reason: str
    source: Literal["glossary", "llm"] = "llm"


class UncertainSegment(BaseModel):
    text: str
    reason: str


class NormalizationRequest(BaseModel):
    session_id: str


class NormalizationResponse(BaseModel):
    session_id: str
    original: str
    normalized: str
    source: Literal["llm_with_glossary", "glossary_only", "demo_prepared"]
    glossary_matches: list[GlossaryMatch] = Field(default_factory=list)
    changes: list[NormalizationChange] = Field(default_factory=list)
    uncertain_segments: list[UncertainSegment] = Field(default_factory=list)
    uncertain_spans: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider: str
    mode: Literal["live", "demo"] = "live"
    disclaimer: str


class LLMNormalization(BaseModel):
    """Strict shape expected from the LLM."""

    normalized_text: str | None = None
    normalized: str | None = None
    changes: list[NormalizationChange] = Field(default_factory=list)
    uncertain_segments: list[UncertainSegment] = Field(default_factory=list)
    uncertain_spans: list[str] = Field(default_factory=list)

    @property
    def final_normalized(self) -> str:
        return (self.normalized_text or self.normalized or "").strip()
