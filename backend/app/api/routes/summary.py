from fastapi import APIRouter, Depends

from app.api.deps import get_sessions
from app.core.exceptions import KothaError
from app.core.session_manager import SessionManager, Stage
from app.schemas.summary import SummaryCard, SummaryRequest
from app.services import summary_generator

router = APIRouter(prefix="/api/summary", tags=["summary"])


@router.post("/generate", response_model=SummaryCard)
def generate(req: SummaryRequest, sessions: SessionManager = Depends(get_sessions)):
    """Assemble the bilingual doctor summary deterministically from stored extraction, safety results, and transcripts."""
    session = sessions.require(req.session_id, Stage.EVALUATED)
    d = session.data
    extraction = session.extraction or d.get("extraction")
    safety = session.safety_result or d.get("safety")
    if extraction is None or safety is None:
        raise KothaError(409, "WORKFLOW_ORDER", "Extraction and safety evaluation must be completed before the summary.")

    original = session.original_transcript or d.get("original", "")
    normalized = session.normalized_transcript or d.get("normalized", "")
    confirmed = session.confirmed_text or d.get("confirmed", "")

    card = summary_generator.generate(
        session_id=session.id,
        mode=session.mode,
        ext=extraction,
        safety=safety,
        original=original,
        normalized=normalized,
        confirmed=confirmed,
        provenance={
            "speech_to_text": d.get("stt_source", session.transcript_source or "speech_recognition"),
            "normalization": d.get("norm_source", "llm_with_glossary"),
            "extraction": d.get("extraction_source", "llm"),
            "red_flags": "deterministic rules",
            "patient_edited_text": "yes" if d.get("edited") else "no",
        },
    )
    session.summary = card
    d["summary"] = card
    session.stage = max(session.stage, Stage.SUMMARIZED)
    return card
