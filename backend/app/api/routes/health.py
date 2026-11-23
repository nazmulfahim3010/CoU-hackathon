import shutil

from fastapi import APIRouter, Depends

from app.api.deps import get_sessions
from app.config import Settings, get_settings
from app.core.session_manager import SessionManager
from app.schemas.transcription import DemoScenario
from app.services import demo_data
from app.services.providers.llm import llm_configured
from app.services.providers.stt import stt_configured

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(s: Settings = Depends(get_settings), sessions: SessionManager = Depends(get_sessions)):
    return {
        "status": "ok",
        "app_mode": s.app_mode,
        "prototype": True,
        "providers": {
            "speech": {
                "configured": stt_configured(s),
                "provider": s.speech_provider,
                "model": s.speech_model,
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
        # every uploaded recording is transcoded with ffmpeg, so live mode cannot work without it
        "ffmpeg": {"available": shutil.which("ffmpeg") is not None},
        "live_mode_ready": stt_configured(s) and llm_configured(s) and shutil.which("ffmpeg") is not None,
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
