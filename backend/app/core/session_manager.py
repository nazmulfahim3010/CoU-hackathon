"""In-memory, TTL-scoped sessions that enforce the workflow order.

Nothing is persisted. Raw audio is never stored here; transcripts exist only
in process memory until the session is deleted or expires.
"""
from __future__ import annotations

import asyncio
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Iterable

from app.core.exceptions import KothaError


class Stage(IntEnum):
    CREATED = 0
    TRANSCRIBED = 1
    NORMALIZED = 2
    CONFIRMED = 3
    EXTRACTED = 4
    EVALUATED = 5
    SAFETY_EVALUATED = 5  # alias
    SUMMARIZED = 6


@dataclass
class Session:
    id: str
    mode: str  # "live" | "demo"
    created_at: float
    expires_at: float
    stage: Stage = Stage.CREATED
    demo_scenario_id: str | None = None

    # Dedicated session fields stored in memory
    original_transcript: str = ""
    transcript_source: str = ""  # "speech_recognition" | "demo_sample" | "typed_by_user"
    normalized_transcript: str = ""
    normalization_notes: list[Any] = field(default_factory=list)
    confirmed_text: str = ""
    extraction: Any = None
    safety_result: Any = None
    summary: Any = None

    # Data dictionary for compatibility with existing service endpoints
    data: dict[str, Any] = field(default_factory=dict)

    def reset_to_created(self) -> None:
        """Reset session back to CREATED and wipe all downstream data."""
        self.stage = Stage.CREATED
        self.original_transcript = ""
        self.transcript_source = ""
        self.normalized_transcript = ""
        self.normalization_notes.clear()
        self.confirmed_text = ""
        self.extraction = None
        self.safety_result = None
        self.summary = None
        self.data.clear()

    def invalidate_after_confirmation(self) -> None:
        """Invalidate CONFIRMED and wipe downstream extractions, safety, and summary."""
        if self.stage >= Stage.CONFIRMED:
            self.stage = Stage.NORMALIZED
        self.confirmed_text = ""
        self.extraction = None
        self.safety_result = None
        self.summary = None
        for k in ("confirmed", "edited", "extraction", "extraction_source", "safety", "summary"):
            self.data.pop(k, None)


class SessionManager:
    def __init__(self, ttl_seconds: int, clock=time.time):
        self._ttl = ttl_seconds
        self._clock = clock
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, mode: str = "live", demo_scenario_id: str | None = None) -> Session:
        with self._lock:
            self._purge_expired_locked()
            now = self._clock()
            sid = str(uuid.uuid4())
            s = Session(
                id=sid,
                mode=mode,
                created_at=now,
                expires_at=now + self._ttl,
                demo_scenario_id=demo_scenario_id,
            )
            self._sessions[sid] = s
            return s

    def get(self, session_id: str) -> Session:
        with self._lock:
            s = self._sessions.get(session_id)
            if s is None:
                raise KothaError(404, "SESSION_NOT_FOUND", "Session not found or expired.")
            if self._clock() >= s.expires_at:
                self._sessions.pop(session_id, None)
                raise KothaError(404, "SESSION_NOT_FOUND", "Session not found or expired.")
            return s

    def require(self, session_id: str, minimum: Stage) -> Session:
        """Enforces that session is at or past minimum stage."""
        s = self.get(session_id)
        if s.stage < minimum:
            code = (
                "CONFIRMATION_REQUIRED"
                if minimum >= Stage.CONFIRMED and s.stage < Stage.CONFIRMED
                else "WORKFLOW_ORDER_VIOLATION"
            )
            raise KothaError(
                409,
                code,
                f"This step requires the '{minimum.name.lower()}' stage; session is at '{s.stage.name.lower()}'.",
            )
        return s

    def require_state(self, session_or_id: Session | str, allowed_states: Stage | Iterable[Stage]) -> Session:
        """Enforces that session is currently in one of allowed_states."""
        s = self.get(session_or_id) if isinstance(session_or_id, str) else session_or_id
        if isinstance(allowed_states, (Stage, int)):
            allowed = {Stage(allowed_states)}
        else:
            allowed = {Stage(x) for x in allowed_states}
        if s.stage not in allowed:
            code = (
                "CONFIRMATION_REQUIRED"
                if (Stage.CONFIRMED in allowed and s.stage < Stage.CONFIRMED)
                else "WORKFLOW_ORDER_VIOLATION"
            )
            allowed_names = [st.name for st in allowed]
            raise KothaError(
                409,
                code,
                f"Workflow order violation: current state '{s.stage.name}' is not in allowed states {allowed_names}.",
            )
        return s

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def purge_expired(self) -> int:
        with self._lock:
            return self._purge_expired_locked()

    def _purge_expired_locked(self) -> int:
        now = self._clock()
        dead = [k for k, v in self._sessions.items() if now >= v.expires_at]
        for k in dead:
            del self._sessions[k]
        return len(dead)

    async def cleanup_loop(self, interval_seconds: int = 60) -> None:
        """Periodic background task that purges expired sessions."""
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                self.purge_expired()
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)
