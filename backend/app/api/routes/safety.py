from fastapi import APIRouter, Depends

from app.api.deps import get_sessions
from app.core.session_manager import SessionManager, Stage
from app.schemas.safety import SafetyRequest, SafetyResponse, SafetyRule
from app.services import red_flag_engine

router = APIRouter(prefix="/api/safety", tags=["safety"])


@router.post("/evaluate", response_model=SafetyResponse)
def evaluate(req: SafetyRequest, sessions: SessionManager = Depends(get_sessions)):
    """Deterministic rules over confirmed text and intake fields. Never calls an LLM.

    Needs only the patient's confirmation, NOT the LLM extraction: a model outage or rate limit must never
    hide an emergency alert."""
    session = sessions.require(req.session_id, Stage.CONFIRMED)
    confirmed = session.confirmed_text or session.data.get("confirmed", "")
    age_group = req.age_group or session.data.get("age_group") or getattr(session, "age_group", None)
    original = session.original_transcript or session.data.get("original", "")

    result = red_flag_engine.evaluate(
        session_id=session.id,
        confirmed_text=confirmed,
        age_group=age_group,
        original_transcript=original,
    )
    result.mode = session.mode
    session.safety_result = result
    session.data["safety"] = result
    session.stage = max(session.stage, Stage.EVALUATED)
    return result


@router.get("/rules", response_model=list[SafetyRule])
def get_rules():
    """Lists all red-flag safety rules for clinical and patient transparency."""
    return red_flag_engine.list_rules()
