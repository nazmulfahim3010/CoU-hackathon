"""In-memory, TTL-bound share store for handing a summary card (and optionally the patient's voice clip)
to a health worker's phone.

Privacy rules (see CLAUDE.md): nothing is written to disk or logs. Records live only in process memory,
are created only after explicit patient/helper consent, expire automatically, and can be revoked.
The share code is an unguessable bearer token (60 bits) with a small failed-lookup rate limit.
"""
from __future__ import annotations

import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from app.core.exceptions import KothaError

# No 0/O/1/I/L to avoid misreading when a code is read aloud or typed on a phone.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 12
MAX_ACTIVE_SHARES = 100
MAX_MISSES_PER_MINUTE = 30


def normalize_code(raw: str) -> str:
    """Accept 'abcd-efgh-jkmn', 'ABCD EFGH JKMN', etc."""
    return "".join(ch for ch in (raw or "").upper() if ch.isalnum())


def format_code(code: str) -> str:
    return "-".join(code[i : i + 4] for i in range(0, len(code), 4))


@dataclass
class ShareRecord:
    code: str
    created_at: float
    expires_at: float
    summary: dict[str, Any]
    mode: str
    audio: bytes | None = None
    audio_mime: str | None = None
    views: int = 0
    meta: dict[str, Any] = field(default_factory=dict)


class ShareStore:
    def __init__(self, ttl_seconds: int, clock=time.time):
        self._ttl = ttl_seconds
        self._clock = clock
        self._records: dict[str, ShareRecord] = {}
        self._misses: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @property
    def ttl_seconds(self) -> int:
        return self._ttl

    def create(self, summary: dict[str, Any], mode: str, audio: bytes | None = None, audio_mime: str | None = None) -> ShareRecord:
        with self._lock:
            self._purge_locked()
            if len(self._records) >= MAX_ACTIVE_SHARES:
                raise KothaError(503, "SHARE_CAPACITY", "Too many active shares right now. Please try again shortly.")
            code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
            while code in self._records:  # astronomically unlikely, but never overwrite
                code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
            now = self._clock()
            rec = ShareRecord(code, now, now + self._ttl, summary, mode, audio, audio_mime)
            self._records[code] = rec
            return rec

    def get(self, raw_code: str, client: str = "unknown", count_view: bool = False) -> ShareRecord:
        code = normalize_code(raw_code)
        with self._lock:
            self._check_rate_locked(client)
            rec = self._records.get(code)
            if rec is None or self._clock() >= rec.expires_at:
                if rec is not None:
                    del self._records[code]
                self._misses[client].append(self._clock())
                # One uniform error: never reveal whether a code ever existed.
                raise KothaError(404, "SHARE_NOT_FOUND", "This share link is invalid or has expired.")
            if count_view:
                rec.views += 1
            return rec

    def delete(self, raw_code: str) -> bool:
        with self._lock:
            return self._records.pop(normalize_code(raw_code), None) is not None

    def purge_expired(self) -> int:
        with self._lock:
            return self._purge_locked()

    def _purge_locked(self) -> int:
        now = self._clock()
        dead = [k for k, v in self._records.items() if now >= v.expires_at]
        for k in dead:
            del self._records[k]
        return len(dead)

    def _check_rate_locked(self, client: str) -> None:
        q = self._misses[client]
        cutoff = self._clock() - 60
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= MAX_MISSES_PER_MINUTE:
            raise KothaError(429, "TOO_MANY_ATTEMPTS", "Too many invalid attempts. Please wait a minute.")
        if not q:
            self._misses.pop(client, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)
