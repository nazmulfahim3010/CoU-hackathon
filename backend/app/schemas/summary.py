from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.safety import RuleResult


class SummarySection(BaseModel):
    key: str
    title_en: str
    title_bn: str
    en: list[str] = Field(default_factory=list)
    bn: list[str] = Field(default_factory=list)
    status: str = "reported"  # reported | not_reported | uncertain | list
    evidence: str | None = None


class SummaryRequest(BaseModel):
    session_id: str


class SummaryCard(BaseModel):
    session_id: str
    generated_at: str
    mode: str
    sections: list[SummarySection] = Field(default_factory=list)
    red_flags: list[RuleResult] = Field(default_factory=list)
    needs_information: list[RuleResult] = Field(default_factory=list)
    original_statement: str = ""
    normalized_statement: str = ""
    confirmed_statement: str = ""
    provenance: dict[str, str] = Field(default_factory=dict)
    label_en: str = "AI-assisted patient intake summary — clinician verification required."
    label_bn: str = "এআই-সহায়তায় তৈরি রোগীর প্রাথমিক তথ্যের সারসংক্ষেপ — চিকিৎসকের যাচাই আবশ্যক।"
    disclaimer_en: str = "Kotha is not a diagnostic tool. Medical decisions must be made by a qualified healthcare professional."
    disclaimer_bn: str = "কথা কোনো রোগ নির্ণয়ের সরঞ্জাম নয়। চিকিৎসা সংক্রান্ত সব সিদ্ধান্ত যোগ্য স্বাস্থ্যসেবা পেশাদারকে নিতে হবে।"


class SpeechRequest(BaseModel):
    session_id: str


class SpeechResponse(BaseModel):
    session_id: str
    text_bn: str
    audio_base64: str
    mime_type: str = "audio/mpeg"
    provider: str
    mode: str = "live"
