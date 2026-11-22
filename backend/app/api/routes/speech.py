from fastapi import APIRouter, Depends

from app.api.deps import get_sessions
from app.config import Settings, get_settings
from app.core.exceptions import KothaError
from app.core.session_manager import SessionManager, Stage
from app.schemas.summary import SpeechRequest, SpeechResponse
from app.services import text_to_speech

router = APIRouter(prefix="/api/speech", tags=["speech"])


@router.post("/generate", response_model=SpeechResponse)
async def generate(req: SpeechRequest, s: Settings = Depends(get_settings), sessions: SessionManager = Depends(get_sessions)):
    """Spoken Bangla reply. Text is template-based (no patient data). Fails honestly if TTS is unavailable."""
    session = sessions.require(req.session_id, Stage.CONFIRMED)
    safety = session.data.get("safety")
    if safety is None:
        raise KothaError(409, "WORKFLOW_ORDER", "Safety evaluation must be completed before the spoken reply.")
    text = text_to_speech.build_spoken_text(bool(safety.triggered))
    audio, mime, provider = await text_to_speech.synthesize(text, s)
    return SpeechResponse(session_id=session.id, text_bn=text, audio_base64=audio, mime_type=mime, provider=provider)


@router.get("/text/{session_id}")
def spoken_text(session_id: str, sessions: SessionManager = Depends(get_sessions)):
    """The reply text alone, so the UI can show it even when audio generation fails."""
    session = sessions.require(session_id, Stage.CONFIRMED)
    safety = session.data.get("safety")
    if safety is None:
        raise KothaError(409, "WORKFLOW_ORDER", "Safety evaluation must be completed first.")
    return {"text_bn": text_to_speech.build_spoken_text(bool(safety.triggered))}
