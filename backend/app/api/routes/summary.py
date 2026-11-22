from fastapi import APIRouter, Depends

from app.api.deps import get_sessions
from app.core.exceptions import KothaError
from app.core.session_manager import SessionManager, Stage
from app.schemas.summary import SummaryCard, SummaryRequest
from app.services import summary_generator

router = APIRouter(prefix="/api/summary", tags=["summary"])


@router.post("/generate", response_model=SummaryCard)
def generate(req: SummaryRequest, sessions: SessionManager = Depends(get_sessions)):
    session = sessions.require(req.session_id, Stage.CONFIRMED)
    d = session.data
    if "extraction" not in d or "safety" not in d:
        raise KothaError(409, "WORKFLOW_ORDER", "Extraction and safety evaluation must be completed before the summary.")
    card = summary_generator.generate(
        session.id, session.mode, d["extraction"], d["safety"], d["original"], d["confirmed"],
        provenance={
            "speech_to_text": d.get("stt_source", ""),
            "normalization": d.get("norm_source", ""),
            "extraction": d.get("extraction_source", ""),
            "red_flags": "deterministic rules",
            "patient_edited_text": "yes" if d.get("edited") else "no",
        },
    )
    d["summary"] = True
    session.stage = max(session.stage, Stage.SUMMARIZED)
    return card
