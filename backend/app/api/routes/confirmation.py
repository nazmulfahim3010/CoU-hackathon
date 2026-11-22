from fastapi import APIRouter, Depends

from app.api.deps import get_sessions
from app.core.exceptions import KothaError
from app.core.session_manager import SessionManager, Stage
from app.schemas.clinical import ConfirmationRequest, ConfirmationResponse
from app.services.glossary_service import clean_text

router = APIRouter(prefix="/api", tags=["confirmation"])
_DOWNSTREAM = ("extraction", "extraction_source", "safety", "summary")


@router.post("/confirmation", response_model=ConfirmationResponse)
def confirmation(req: ConfirmationRequest, sessions: SessionManager = Depends(get_sessions)):
    """Mandatory patient/helper confirmation gate. Extraction cannot run until this succeeds."""
    session = sessions.require(req.session_id, Stage.NORMALIZED)
    if not req.confirmed:
        raise KothaError(400, "NOT_CONFIRMED", "The transcript must be explicitly confirmed.")
    original, confirmed = clean_text(req.original_text), clean_text(req.confirmed_text)
    if not confirmed:
        raise KothaError(422, "EMPTY_TEXT", "The confirmed text is empty.")
    edited = confirmed != session.data["normalized"] or original != session.data["original"]
    session.data["original"] = original
    session.data["confirmed"] = confirmed
    session.data["edited"] = edited
    for k in _DOWNSTREAM:  # re-confirmation invalidates anything derived from older text
        session.data.pop(k, None)
    session.stage = Stage.CONFIRMED
    return ConfirmationResponse(session_id=session.id, stage=session.stage.name.lower(), edited_by_patient=edited)
