from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_sessions
from app.api.routes import confirmation, extraction, health, normalization, safety, speech, summary, transcription
from app.config import get_settings
from app.core.exceptions import install_handlers
from app.core.session_manager import SessionManager


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Kotha API",
        version="0.1.0",
        description=(
            "Dialect-to-clinical-note voice assistant (hackathon prototype). "
            "Not a diagnostic tool and not a certified medical system. Nothing is persisted."
        ),
    )
    app.state.sessions = SessionManager(s.session_ttl_seconds)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in s.cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_handlers(app)
    for r in (health, transcription, normalization, confirmation, extraction, safety, summary, speech):
        app.include_router(r.router)

    @app.delete("/api/session/{session_id}", tags=["session"], status_code=204)
    def end_session(session_id: str, sessions: SessionManager = Depends(get_sessions)):
        """Discard all session data immediately."""
        sessions.delete(session_id)

    return app


app = create_app()
