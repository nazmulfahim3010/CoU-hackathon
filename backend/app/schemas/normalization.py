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
    # Traceability: which glossary row produced this suggestion, and how it matched
    glossary_id: str | None = None
    verification_status: str | None = None
    matching_method: str = "exact_word"  # exact_word | exact_phrase | word_boundary


class NormalizationChange(BaseModel):
    original: str
    normalized: str
    reason: str
    source: Literal["glossary", "llm"] = "llm"
    glossary_id: str | None = None
    category: str | None = None
    verification_status: str | None = None
    matching_method: str | None = None
    glossary_evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("source", mode="before")
    @classmethod
    def normalize_source(cls, v: str) -> str:
        if isinstance(v, str) and "glossary" in v.lower():
            return "glossary"
        return "llm"


class GlossaryEvidence(BaseModel):
    """One glossary row that influenced (or was available to) a normalization."""

    glossary_id: str | None
    regional_expression: str
    standard_bangla: str
    category: str
    verification_status: str
    matching_method: str
    applied: bool = True  # False when the row matched but the final text does not use its standard form


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
    glossary_evidence: list[GlossaryEvidence] = Field(default_factory=list)
    # glossary_only_proposal | no_glossary_match_unchanged | llm_proposal_validated | llm_rejected_glossary_fallback
    normalization_status: str = "glossary_only_proposal"
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
