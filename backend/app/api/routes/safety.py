from fastapi import APIRouter, Depends

from app.api.deps import get_sessions
from app.core.session_manager import SessionManager, Stage
from app.schemas.safety import SafetyRequest, SafetyResponse
from app.services import red_flag_engine

router = APIRouter(prefix="/api/safety", tags=["safety"])


@router.post("/evaluate", response_model=SafetyResponse)
def evaluate(req: SafetyRequest, sessions: SessionManager = Depends(get_sessions)):
    """Deterministic rules over the confirmed text. Never calls an LLM."""
    session = sessions.require(req.session_id, Stage.CONFIRMED)
    result = red_flag_engine.evaluate(session.id, session.data["confirmed"])
    session.data["safety"] = result
    session.stage = max(session.stage, Stage.SAFETY_EVALUATED)
    return result
