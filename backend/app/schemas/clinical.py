from typing import Literal

from pydantic import BaseModel, Field, model_validator

Status = Literal["reported", "not_reported", "uncertain"]


class BilingualField(BaseModel):
    """A single clinical field. `not_reported` never means 'absent'."""

    status: Status
    bn: str | None = None
    en: str | None = None
    # Verbatim quote from the patient's confirmed text that supports this value (checked by grounding.py)
    evidence: str | None = None

    @model_validator(mode="after")
    def _consistent(self):
        has_value = bool((self.bn or "").strip() or (self.en or "").strip())
        if self.status == "not_reported" and has_value:
            raise ValueError("not_reported fields must not carry a value")
        if self.status in ("reported", "uncertain") and not has_value:
            raise ValueError(f"{self.status} fields must carry a value")
        return self


class Item(BaseModel):
    bn: str = Field(min_length=1)
    en: str = Field(min_length=1)
    # Verbatim quote from the patient's confirmed text; items without a real quote are removed
    evidence: str | None = None


class ClinicalExtraction(BaseModel):
    chief_complaint: BilingualField
    symptoms: list[Item] = Field(default_factory=list)
    duration: BilingualField
    severity: BilingualField
    relevant_history: BilingualField
    current_medications: BilingualField
    allergies: BilingualField
    associated_symptoms: list[Item] = Field(default_factory=list)
    negative_symptoms: list[Item] = Field(default_factory=list)
    uncertain_or_missing: list[Item] = Field(default_factory=list)
    model_noted_red_flag_indicators: list[Item] = Field(default_factory=list)
    # What the model proposed but the patient never said (removed; shown to the clinician for transparency)
    removed_ungrounded: list[Item] = Field(default_factory=list)


class ExtractionRequest(BaseModel):
    session_id: str


class ExtractionResponse(BaseModel):
    session_id: str
    source: Literal["llm", "demo_prepared", "cached_demo_output"]
    provider: str
    extraction: ClinicalExtraction
    note: str
    mode: str = "live"


class ConfirmationRequest(BaseModel):
    session_id: str
    confirmed_text: str = Field(min_length=1, max_length=5000)
    original_text: str | None = Field(default=None, max_length=5000)
    edited: bool | None = None
    confirmed_by: Literal["patient", "helper"] = "patient"
    confirmed: bool = True


class ConfirmationResponse(BaseModel):
    session_id: str
    stage: str
    confirmed_text: str
    edited_by_patient: bool
    confirmed_by: Literal["patient", "helper"] = "patient"
    warnings: list[str] = Field(default_factory=list)
    mode: str = "live"
