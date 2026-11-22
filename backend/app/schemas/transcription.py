from typing import Literal

from pydantic import BaseModel

Source = Literal["speech_model", "demo_prepared_text"]


class TranscriptionResponse(BaseModel):
    session_id: str
    mode: Literal["live", "demo"]
    transcript: str
    source: Source
    provider: str
    model: str | None = None
    confidence: float | None = None  # only when the model genuinely reports it
    disclaimer: str


class DemoScenario(BaseModel):
    id: str
    title: str
    purpose: str
    dialect_label: str
    patient_note: str
