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
    share,
    speech,
    summary,
    transcription,
)
from app.config import get_settings
from app.core.exceptions import install_handlers
from app.core.session_manager import SessionManager
from app.core.share_store import ShareStore


async def _share_cleanup(shares: ShareStore, interval_seconds: int = 30) -> None:
    """Purge expired shares (and the voice clips they hold) from memory."""
    while True:
        await asyncio.sleep(interval_seconds)
        shares.purge_expired()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Background task for periodic session TTL cleanup
    cleanup_task = asyncio.create_task(app.state.sessions.cleanup_loop(interval_seconds=60))
    share_task = asyncio.create_task(_share_cleanup(app.state.shares))
    yield
    for task in (cleanup_task, share_task):
        task.cancel()
        try:
            await task
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
    app.state.shares = ShareStore(s.share_ttl_minutes * 60)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in s.cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_handlers(app)
    for r in (health, session, transcription, normalization, confirmation, extraction, safety, summary, speech, demo, share):
        app.include_router(r.router)

    @app.get("/")
    def root():
        return {
            "app": "Kotha (কথা) API",
            "version": "0.1.0",
            "status": "online",
            "message": "Backend API is running. Visit the frontend UI or Swagger documentation below.",
            "frontend_url": "http://127.0.0.1:5173/",
            "docs_url": "http://127.0.0.1:8000/docs",
            "health_url": "http://127.0.0.1:8000/api/health",
        }

    return app


app = create_app()
