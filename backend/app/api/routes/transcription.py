from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import get_sessions
from app.config import Settings, get_settings
from app.core.exceptions import KothaError
from app.core.logging import get_logger
from app.core.security import validate_audio
from app.core.session_manager import SessionManager, Stage
from app.schemas.transcription import TranscriptionResponse
from app.services import demo_data
from app.services.glossary_service import clean_text
from app.services.providers.stt import get_stt

router = APIRouter(prefix="/api", tags=["transcription"])
log = get_logger("transcription")


@router.post("/transcription", response_model=TranscriptionResponse)
async def transcribe(
    audio: UploadFile | None = File(default=None),
    demo_scenario_id: str | None = Form(default=None),
    s: Settings = Depends(get_settings),
    sessions: SessionManager = Depends(get_sessions),
):
    """Create a session and transcribe audio (live) or load a prepared sample text (demo)."""
    if demo_scenario_id:
        scenario = demo_data.get_scenario(demo_scenario_id)
        session = sessions.create("demo", demo_scenario_id)
        session.data["original"] = scenario["original"]
        session.data["stt_source"] = "demo_prepared_text"
        session.stage = Stage.TRANSCRIBED
        return TranscriptionResponse(
            session_id=session.id, mode="demo", transcript=scenario["original"], source="demo_prepared_text",
            provider="demo", model=None, confidence=None,
            disclaimer="DEMO: prepared sample text. This was NOT produced by speech recognition.",
        )

    if audio is None:
        raise KothaError(400, "NO_INPUT", "Provide an audio file or a demo_scenario_id.")
    data = await audio.read()
    validate_audio(data, s.max_audio_bytes)
    stt = get_stt(s)  # 503 if not configured, before a session is created
    result = await stt.transcribe(data, audio.content_type or "audio/webm")
    del data  # audio is never stored
    text = clean_text(result.text)
    if not text:
        raise KothaError(422, "NO_SPEECH_DETECTED", "No speech was detected. Please record again, closer to the microphone.")
    session = sessions.create("live")
    session.data["original"] = text
    session.data["stt_source"] = "speech_model"
    session.stage = Stage.TRANSCRIBED
    log.info("transcribed session=%s provider=%s", session.id[:6], result.provider)
    return TranscriptionResponse(
        session_id=session.id, mode="live", transcript=text, source="speech_model", provider=result.provider,
        model=result.model, confidence=result.confidence,
        disclaimer="Speech recognition for regional dialects is unreliable. Please check the text carefully.",
    )
