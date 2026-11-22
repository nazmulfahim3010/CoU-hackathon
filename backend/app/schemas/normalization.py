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


class NormalizationRequest(BaseModel):
    session_id: str


class NormalizationResponse(BaseModel):
    session_id: str
    original: str
    normalized: str
    source: Literal["llm_with_glossary", "glossary_only", "demo_prepared"]
    glossary_matches: list[GlossaryMatch]
    uncertain_spans: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider: str
    disclaimer: str


class LLMNormalization(BaseModel):
    """Strict shape expected from the LLM."""

    normalized: str = Field(min_length=1)
    uncertain_spans: list[str] = Field(default_factory=list)
