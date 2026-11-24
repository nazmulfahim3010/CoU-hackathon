from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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

    @field_validator("source", mode="before")
    @classmethod
    def normalize_source(cls, v: str) -> str:
        if isinstance(v, str) and "glossary" in v.lower():
            return "glossary"
        return "llm"


class UncertainSegment(BaseModel):
    text: str
    reason: str


class NormalizationRequest(BaseModel):
    session_id: str


class NormalizationResponse(BaseModel):
    session_id: str
    original: str
    original_text: str | None = None
    transliterated_text: str | None = None
    script_type: Literal["bangla_script", "romanized", "mixed"] = "bangla_script"
    normalized: str
    source: Literal["llm_with_glossary", "glossary_only", "demo_prepared", "cached_demo_output"]
    glossary_matches: list[GlossaryMatch] = Field(default_factory=list)
    changes: list[NormalizationChange] = Field(default_factory=list)
    uncertain_segments: list[UncertainSegment] = Field(default_factory=list)
    uncertain_spans: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provider: str
    mode: Literal["live", "demo"] = "live"
    disclaimer: str

    @model_validator(mode="after")
    def _sync_original(self):
        if self.original_text is None:
            self.original_text = self.original
        return self


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
