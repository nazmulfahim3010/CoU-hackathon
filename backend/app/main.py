import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_sessions
from app.api.routes import (
    confirmation,
    demo,
    extraction,
    health,
    normalization,
    safety,
    session,
    speech,
    summary,
    transcription,
)
from app.config import get_settings
from app.core.exceptions import install_handlers
from app.core.session_manager import SessionManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Background task for periodic session TTL cleanup
    cleanup_task = asyncio.create_task(app.state.sessions.cleanup_loop(interval_seconds=60))
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Kotha API",
        version="0.1.0",
        description=(
            "Dialect-to-clinical-note voice assistant (hackathon prototype). "
            "Not a diagnostic tool and not a certified medical system. Nothing is persisted."
        ),
        lifespan=lifespan,
    )
    ttl_seconds = s.session_ttl_minutes * 60 if s.session_ttl_minutes else s.session_ttl_seconds
    app.state.sessions = SessionManager(ttl_seconds)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in s.cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_handlers(app)
    for r in (health, session, transcription, normalization, confirmation, extraction, safety, summary, speech, demo):
        app.include_router(r.router)

    return app


app = create_app()
