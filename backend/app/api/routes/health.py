import shutil

from fastapi import APIRouter, Depends

from app.api.deps import get_sessions
from app.config import Settings, get_settings
from app.core.session_manager import SessionManager
from app.schemas.transcription import DemoScenario
from app.services import demo_data
from app.services.llm_provider import llm_configured
from app.services.speech_to_text import effective_speech_model, stt_configured

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(s: Settings = Depends(get_settings), sessions: SessionManager = Depends(get_sessions)):
    ffmpeg_ok = bool(shutil.which("ffmpeg"))
    return {
        "status": "ok",
        "app_mode": s.app_mode,
        "prototype": True,
        "ffmpeg": {
            "available": ffmpeg_ok,
        },
        "providers": {
            "speech": {
                "configured": stt_configured(s),
                "provider": s.speech_provider,
                "model": effective_speech_model(s),
            },
            "llm": {
                "configured": llm_configured(s),
                "provider": s.llm_provider,
            },
            "tts": {
                "configured": s.tts_provider == "gtts",
                "provider": s.tts_provider,
            },
        },
        "live_mode_ready": ffmpeg_ok and stt_configured(s) and llm_configured(s),
        "active_sessions": len(sessions),
    }


@router.get("/demo/scenarios", response_model=list[DemoScenario])
def demo_scenarios():
    return [
        DemoScenario(
            id=x["id"],
            title=x["title"],
            purpose=x["purpose"],
            dialect_label=x["dialect_label"],
            patient_note=x["patient_note"],
        )
        for x in demo_data.list_scenarios()
    ]
