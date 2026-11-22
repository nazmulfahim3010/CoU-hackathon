from fastapi import APIRouter, Depends

from app.api.deps import get_sessions
from app.config import Settings, get_settings
from app.core.exceptions import KothaError
from app.core.session_manager import SessionManager, Stage
from app.schemas.summary import SpeechRequest, SpeechResponse
from app.services import text_to_speech

router = APIRouter(prefix="/api/speech", tags=["speech"])


def _extract_spoken_params(session) -> tuple[bool, list]:
    safety = session.safety_result or session.data.get("safety")
    extraction = session.extraction or session.data.get("extraction")

    has_urgent = False
    if safety:
        triggered = getattr(safety, "triggered", [])
        has_urgent = any(
            getattr(r, "alert_level", "") in ("emergency", "urgent")
            for r in triggered
        ) or bool(triggered)

    missing = []
    if extraction:
        missing = getattr(extraction, "uncertain_or_missing", [])

    return has_urgent, missing


@router.post("/generate", response_model=SpeechResponse)
async def generate(
    req: SpeechRequest,
    s: Settings = Depends(get_settings),
    sessions: SessionManager = Depends(get_sessions),
):
    """Spoken Bangla reply. Built from deterministic patient-safe template. Audio synthesized in memory only."""
    session = sessions.require(req.session_id, Stage.SUMMARIZED)
    has_urgent, missing = _extract_spoken_params(session)
    text = text_to_speech.build_spoken_template_text(has_urgent, missing)

    audio_base64, mime_type, provider = await text_to_speech.synthesize(text, s)
    return SpeechResponse(
        session_id=session.id,
        text_bn=text,
        audio_base64=audio_base64,
        mime_type=mime_type,
        provider=provider,
        mode=session.mode,
    )


@router.get("/text/{session_id}")
def spoken_text(session_id: str, sessions: SessionManager = Depends(get_sessions)):
    """The reply text alone, so the UI can display it even when audio generation fails or is offline."""
    session = sessions.require(session_id, Stage.CONFIRMED)
    has_urgent, missing = _extract_spoken_params(session)
    return {"text_bn": text_to_speech.build_spoken_template_text(has_urgent, missing)}
