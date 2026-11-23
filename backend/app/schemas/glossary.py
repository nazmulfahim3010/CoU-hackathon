from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

GlossaryCategory = Literal[
    "body_part",
    "symptom",
    "pain_description",
    "fever",
    "time_expression",
    "severity",
    "common_medical",
]


class GlossaryEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    regional_expression: str = Field(validation_alias="regional_expression")
    standard_bangla: str = Field(validation_alias="standard_bangla")
    english_meaning: str = Field(validation_alias="english_meaning")
    dialect: str
    category: GlossaryCategory
    example_sentence: str = Field(default="", validation_alias="example_sentence")
    verification_status: Literal["verified", "unverified"] = Field(
        default="unverified", validation_alias="verification_status"
    )
    source: str = Field(default="Team draft")
    contributor: str | None = None
    # Verification audit trail. Only ever copied from the source data, never inferred.
    verified_by: str | None = None
    verification_date: str | None = None
    verification_note: str | None = None

    @classmethod
    def from_raw(cls, data: dict, default_dialect: str = "unknown", idx: int = 1) -> "GlossaryEntry":
        """Accepts either canonical or legacy alias fields."""
        reg = (data.get("regional_expression") or data.get("regional") or data.get("term") or "").strip()
        std = (data.get("standard_bangla") or data.get("standard") or data.get("term") or "").strip()
        eng = data.get("english_meaning") or data.get("english") or ""
        cat = data.get("category", "common_medical")
        if cat == "severity_expression":
            cat = "severity"
        elif cat == "fever_related":
            cat = "fever"
        elif cat not in ("body_part", "symptom", "pain_description", "fever", "time_expression", "severity", "common_medical"):
            cat = "common_medical"

        eid = data.get("id") or f"{data.get('dialect', default_dialect)}_{idx:03d}"
        v_status = data.get("verification_status") or data.get("verification") or "unverified"
        if v_status not in ("verified", "unverified"):
            v_status = "unverified"

        return cls(
            id=eid,
            regional_expression=reg,
            standard_bangla=std,
            english_meaning=eng,
            dialect=data.get("dialect", default_dialect),
            category=cat,  # type: ignore[arg-type]
            example_sentence=data.get("example_sentence") or data.get("example") or "",
            verification_status=v_status,  # type: ignore[arg-type]
            source=data.get("source", "Team draft"),
            contributor=data.get("contributor") or None,
            verified_by=(data.get("verified_by") or "").strip() or None,
            verification_date=(data.get("verification_date") or "").strip() or None,
            verification_note=(data.get("verification_note") or "").strip() or None,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "regional_expression": self.regional_expression,
            "regional": self.regional_expression,
            "standard_bangla": self.standard_bangla,
            "standard": self.standard_bangla,
            "english_meaning": self.english_meaning,
            "english": self.english_meaning,
            "dialect": self.dialect,
            "category": self.category,
            "example_sentence": self.example_sentence,
            "example": self.example_sentence,
            "verification_status": self.verification_status,
            "verification": self.verification_status,
            "source": self.source,
            "contributor": self.contributor,
            "verified_by": self.verified_by,
            "verification_date": self.verification_date,
            "verification_note": self.verification_note,
        }


class DialectCount(BaseModel):
    total: int
    verified: int
    unverified: int


class GlossaryStatsResponse(BaseModel):
    total_entries: int
    by_dialect: dict[str, DialectCount]
    verified_total: int
    unverified_total: int
    disclaimer: str
