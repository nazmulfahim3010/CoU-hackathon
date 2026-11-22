from typing import Literal

from pydantic import BaseModel, Field

Source = Literal["speech_recognition", "speech_model", "demo_prepared_text", "demo_sample", "typed_by_user"]


class TranscriptionResponse(BaseModel):
    session_id: str
    mode: Literal["live", "demo"]
    transcript: str
    source: Source
    provider: str
    model: str | None = None
    duration_seconds: float | None = None
    confidence: float | None = None  # only when genuinely reported by the provider
    disclaimer: str


class TypedTranscriptionRequest(BaseModel):
    session_id: str
    text: str = Field(min_length=1)
    dialect_hint: str | None = None


class DemoScenario(BaseModel):
    id: str
    title: str
    purpose: str
    dialect_label: str
    patient_note: str
