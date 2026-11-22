from fastapi import APIRouter, Depends

from app.api.deps import get_sessions
from app.core.exceptions import KothaError
from app.core.session_manager import SessionManager, Stage
from app.schemas.clinical import ConfirmationRequest, ConfirmationResponse
from app.services.dialect_normalizer import check_meaning_preservation
from app.services.glossary_service import clean_text

router = APIRouter(prefix="/api", tags=["confirmation"])
_DOWNSTREAM = ("extraction", "extraction_source", "safety", "summary")


@router.post("/confirmation", response_model=ConfirmationResponse)
def confirmation(req: ConfirmationRequest, sessions: SessionManager = Depends(get_sessions)):
    """Mandatory patient/helper confirmation gate. Extraction cannot run until this succeeds."""
    # Requires minimum stage NORMALIZED (Stage 2)
    session = sessions.require(req.session_id, Stage.NORMALIZED)
    if not req.confirmed:
        raise KothaError(400, "NOT_CONFIRMED", "The transcript must be explicitly confirmed.")

    confirmed = clean_text(req.confirmed_text)
    if not confirmed:
        raise KothaError(422, "EMPTY_TEXT", "The confirmed text cannot be empty.")
    if len(confirmed) > 5000:
        raise KothaError(413, "TEXT_TOO_LONG", "The confirmed text exceeds the 5,000 character limit.")

    original = clean_text(req.original_text) if req.original_text else session.data.get("original", "")
    normalized_prev = session.data.get("normalized", "")

    edited = (
        bool(req.edited)
        if req.edited is not None
        else (confirmed != normalized_prev or (bool(original) and original != session.data.get("original", "")))
    )

    session.data["original"] = original or session.data.get("original", "")
    session.data["confirmed"] = confirmed
    session.confirmed_text = confirmed
    session.data["edited"] = edited
    session.data["confirmed_by"] = req.confirmed_by

    # Re-running deterministic checks on edited text for advisory warnings (never overwriting confirmed text)
    warnings: list[str] = []
    if original and confirmed:
        problems = check_meaning_preservation(original, confirmed)
        if problems:
            warnings.append(f"Notice: Edited text changes clinical details: {', '.join(problems)}.")
    session.data["confirmation_warnings"] = warnings

    # Clear downstream extractions/summaries so they are never derived from stale or unconfirmed text
    for k in _DOWNSTREAM:
        session.data.pop(k, None)
    session.extraction = None
    session.safety_result = None
    session.summary = None

    session.stage = Stage.CONFIRMED
    return ConfirmationResponse(
        session_id=session.id,
        stage=session.stage.name.lower(),
        confirmed_text=confirmed,
        edited_by_patient=edited,
        confirmed_by=req.confirmed_by,
        warnings=warnings,
        mode=session.mode,
    )
