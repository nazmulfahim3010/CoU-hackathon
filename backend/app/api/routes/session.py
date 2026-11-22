from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_sessions
from app.core.session_manager import SessionManager

router = APIRouter(prefix="/api", tags=["session"])


class CreateSessionRequest(BaseModel):
    mode: str = Field(default="live", pattern="^(live|demo)$")
    demo_scenario_id: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    state: str
    expires_at: float
    mode: str


@router.post("/session", response_model=SessionResponse, status_code=201)
def create_session(
    req: CreateSessionRequest | None = None,
    sessions: SessionManager = Depends(get_sessions),
):
    mode = req.mode if req else "live"
    scenario_id = req.demo_scenario_id if req else None
    session = sessions.create(mode=mode, demo_scenario_id=scenario_id)
    return SessionResponse(
        session_id=session.id,
        state=session.stage.name,
        expires_at=session.expires_at,
        mode=session.mode,
    )


@router.delete("/session/{session_id}", status_code=204)
def end_session(session_id: str, sessions: SessionManager = Depends(get_sessions)):
    """Discard all session data immediately."""
    sessions.delete(session_id)
