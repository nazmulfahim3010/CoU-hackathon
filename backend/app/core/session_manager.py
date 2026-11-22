"""In-memory, TTL-scoped sessions that enforce the workflow order.

Nothing is persisted. Raw audio is never stored here; transcripts exist only
in process memory until the session is deleted or expires.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from app.core.exceptions import KothaError


class Stage(IntEnum):
    CREATED = 0
    TRANSCRIBED = 1
    NORMALIZED = 2
    CONFIRMED = 3
    EXTRACTED = 4
    SAFETY_EVALUATED = 5
    SUMMARIZED = 6


@dataclass
class Session:
    id: str
    mode: str  # "live" | "demo"
    created_at: float
    expires_at: float
    stage: Stage = Stage.CREATED
    demo_scenario_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


class SessionManager:
    def __init__(self, ttl_seconds: int, clock=time.time):
        self._ttl = ttl_seconds
        self._clock = clock
        self._sessions: dict[str, Session] = {}

    def create(self, mode: str, demo_scenario_id: str | None = None) -> Session:
        self.purge_expired()
        now = self._clock()
        s = Session(secrets.token_urlsafe(24), mode, now, now + self._ttl, demo_scenario_id=demo_scenario_id)
        self._sessions[s.id] = s
        return s

    def get(self, session_id: str) -> Session:
        s = self._sessions.get(session_id)
        if s is None:
            raise KothaError(404, "SESSION_NOT_FOUND", "Session not found or expired.")
        if self._clock() >= s.expires_at:
            self._sessions.pop(session_id, None)
            raise KothaError(404, "SESSION_NOT_FOUND", "Session not found or expired.")
        return s

    def require(self, session_id: str, minimum: Stage) -> Session:
        s = self.get(session_id)
        if s.stage < minimum:
            code = "CONFIRMATION_REQUIRED" if minimum >= Stage.CONFIRMED and s.stage < Stage.CONFIRMED else "WORKFLOW_ORDER"
            raise KothaError(
                409,
                code,
                f"This step requires the '{minimum.name.lower()}' stage; session is at '{s.stage.name.lower()}'.",
            )
        return s

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def purge_expired(self) -> int:
        now = self._clock()
        dead = [k for k, v in self._sessions.items() if now >= v.expires_at]
        for k in dead:
            del self._sessions[k]
        return len(dead)

    def __len__(self) -> int:
        return len(self._sessions)
