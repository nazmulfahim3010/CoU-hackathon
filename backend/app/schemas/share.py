from __future__ import annotations

from pydantic import BaseModel

from app.schemas.summary import SummaryCard


class ShareCreated(BaseModel):
    code: str  # compact, e.g. ABCDEFGHJKMN
    display_code: str  # grouped for reading aloud, e.g. ABCD-EFGH-JKMN
    share_path: str  # e.g. /s/ABCDEFGHJKMN
    share_url: str  # absolute when PUBLIC_BASE_URL is configured, else same as share_path
    expires_at: float  # unix seconds
    ttl_seconds: int
    has_audio: bool
    notice: str


class SharedSummary(BaseModel):
    code: str
    summary: SummaryCard
    has_audio: bool
    mode: str
    created_at: float
    expires_at: float
    seconds_left: int
    views: int
    notice: str
