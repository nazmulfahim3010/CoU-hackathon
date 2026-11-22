from pydantic import BaseModel

from app.schemas.safety import RuleResult


class SummarySection(BaseModel):
    key: str
    title_en: str
    title_bn: str
    en: list[str]
    bn: list[str]
    status: str  # reported | not_reported | uncertain | list


class SummaryRequest(BaseModel):
    session_id: str


class SummaryCard(BaseModel):
    session_id: str
    generated_at: str
    mode: str
    sections: list[SummarySection]
    red_flags: list[RuleResult]
    needs_information: list[RuleResult]
    original_statement: str
    normalized_statement: str
    provenance: dict[str, str]
    label_en: str
    label_bn: str
    disclaimer_en: str
    disclaimer_bn: str


class SpeechRequest(BaseModel):
    session_id: str


class SpeechResponse(BaseModel):
    session_id: str
    text_bn: str
    audio_base64: str
    mime_type: str
    provider: str
