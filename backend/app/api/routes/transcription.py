from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import get_sessions
from app.config import Settings, get_settings
from app.core.exceptions import KothaError
from app.core.logging import get_logger
from app.core.security import validate_audio
from app.core.session_manager import SessionManager, Stage
from app.schemas.transcription import (
    TranscriptionResponse,
    TypedTranscriptionRequest,
)
from app.services import demo_data
from app.services.glossary_service import clean_text
from app.services.speech_to_text import get_stt, process_audio

router = APIRouter(prefix="/api", tags=["transcription"])
log = get_logger("transcription")


@router.post("/transcription", response_model=TranscriptionResponse)
async def transcribe(
    session_id: str | None = Form(default=None),
    audio: UploadFile | None = File(default=None),
    dialect_hint: str | None = Form(default=None),
    demo_scenario_id: str | None = Form(default=None),
    s: Settings = Depends(get_settings),
    sessions: SessionManager = Depends(get_sessions),
):
    """Create a session (or validate state CREATED) and transcribe audio or load a prepared demo sample."""
    if demo_scenario_id:
        scenario = demo_data.get_scenario(demo_scenario_id)
        if session_id:
            session = sessions.require_state(session_id, [Stage.CREATED])
            session.mode = "demo"
            session.demo_scenario_id = demo_scenario_id
        else:
            session = sessions.create("demo", demo_scenario_id)
        session.original_transcript = scenario["original"]
        session.transcript_source = "demo_sample"
        session.data["original"] = scenario["original"]
        session.data["stt_source"] = "demo_sample"
        session.stage = Stage.TRANSCRIBED
        return TranscriptionResponse(
            session_id=session.id,
            mode="demo",
            transcript=scenario["original"],
            source="demo_sample",
            provider="demo",
            model=None,
            duration_seconds=None,
            confidence=None,
            disclaimer="DEMO: prepared sample text. This was NOT produced by speech recognition.",
        )

    if session_id:
        session = sessions.require_state(session_id, [Stage.CREATED])
    else:
        session = None

    if audio is None:
        raise KothaError(400, "NO_INPUT", "Provide an audio file or a demo_scenario_id.")

    raw_data = await audio.read()
    validate_audio(raw_data, s.max_audio_bytes)
    stt = get_stt(s)  # Raises 503 if not configured

    wav_bytes, duration = process_audio(raw_data, s.max_audio_bytes)
    del raw_data

    result = await stt.transcribe(wav_bytes, "audio/wav")
    del wav_bytes

    text = clean_text(result.text)
    if not text:
        raise KothaError(422, "NO_SPEECH_DETECTED", "No speech was detected. Please record again, closer to the microphone.")

    if session is None:
        session = sessions.create("live")

    session.original_transcript = text
    session.transcript_source = "speech_recognition"
    session.data["original"] = text
    session.data["stt_source"] = "speech_recognition"
    if dialect_hint:
        session.data["dialect_hint"] = dialect_hint
    session.stage = Stage.TRANSCRIBED

    log.info("transcribed session=%s provider=%s duration=%.1fs", session.id[:6], result.provider, duration)
    return TranscriptionResponse(
        session_id=session.id,
        mode="live",
        transcript=text,
        source="speech_recognition",
        provider=result.provider,
        model=result.model,
        duration_seconds=round(duration, 2),
        confidence=result.confidence,
        disclaimer="Speech recognition for regional dialects is unreliable. Please check the text carefully.",
    )


@router.post("/transcription/typed", response_model=TranscriptionResponse)
def transcribe_typed(
    req: TypedTranscriptionRequest,
    sessions: SessionManager = Depends(get_sessions),
):
    """Fallback manual transcript when ASR is unavailable or fails."""
    session = sessions.require_state(req.session_id, [Stage.CREATED])
    text = clean_text(req.text)
    if not text:
        raise KothaError(422, "EMPTY_TEXT", "Typed transcript cannot be empty.")

    session.original_transcript = text
    session.transcript_source = "typed_by_user"
    session.data["original"] = text
    session.data["stt_source"] = "typed_by_user"
    if req.dialect_hint:
        session.data["dialect_hint"] = req.dialect_hint
    session.stage = Stage.TRANSCRIBED

    log.info("transcription_typed session=%s", session.id[:6])
    return TranscriptionResponse(
        session_id=session.id,
        mode=session.mode,
        transcript=text,
        source="typed_by_user",
        provider="manual",
        model=None,
        duration_seconds=None,
        confidence=1.0,
        disclaimer="This transcript was typed by the patient or helper.",
    )
