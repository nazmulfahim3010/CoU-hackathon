"""Consent-based sharing of the summary card (and optionally the voice clip) with a health worker."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response

from app.api.deps import get_sessions, get_shares
from app.config import Settings, get_settings
from app.core.exceptions import KothaError
from app.core.logging import get_logger
from app.core.security import validate_audio
from app.core.session_manager import SessionManager, Stage
from app.core.share_store import ShareStore, format_code, normalize_code
from app.schemas.share import ShareCreated, SharedSummary
from app.schemas.summary import SummaryCard

router = APIRouter(prefix="/api/share", tags=["share"])
log = get_logger("share")

NOTICE_EN = (
    "Shared with the patient's consent. Held in memory only, deleted when it expires or is revoked. "
    "Kotha is not a diagnostic tool: the health worker must verify everything."
)
_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def _client(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown"))


def _truthy(v: str | bool | None) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


@router.post("", response_model=ShareCreated, status_code=201)
async def create_share(
    session_id: str = Form(...),
    consent: str = Form(...),
    include_audio: str = Form("false"),
    audio: UploadFile | None = File(default=None),
    s: Settings = Depends(get_settings),
    sessions: SessionManager = Depends(get_sessions),
    shares: ShareStore = Depends(get_shares),
):
    """Create a short-lived share. Requires a finished summary AND explicit consent; the voice clip is
    only kept if the patient chose to include it, and only in memory until the share expires."""
    if not _truthy(consent):
        raise KothaError(400, "CONSENT_REQUIRED", "The patient or helper must explicitly consent to sharing.")
    session = sessions.require(session_id, Stage.SUMMARIZED)
    card = session.summary or session.data.get("summary")
    if not isinstance(card, SummaryCard):
        raise KothaError(409, "WORKFLOW_ORDER_VIOLATION", "Generate the summary before sharing it.")

    audio_bytes: bytes | None = None
    audio_mime: str | None = None
    if _truthy(include_audio):
        if audio is None:
            raise KothaError(400, "AUDIO_REQUIRED", "include_audio was set but no audio was provided.")
        audio_bytes = await audio.read()
        validate_audio(audio_bytes, s.effective_max_audio_bytes)
        audio_mime = audio.content_type or "audio/webm"
    elif audio is not None:
        await audio.read()  # drain and discard: audio is never kept without include_audio

    rec = shares.create(card.model_dump(mode="json"), session.mode, audio_bytes, audio_mime)
    log.info("share_created code=%s audio=%s", rec.code[:4], bool(audio_bytes))
    path = f"/s/{rec.code}"
    base = s.public_base_url.rstrip("/")
    return ShareCreated(
        code=rec.code,
        display_code=format_code(rec.code),
        share_path=path,
        share_url=f"{base}{path}" if base else path,
        expires_at=rec.expires_at,
        ttl_seconds=shares.ttl_seconds,
        has_audio=audio_bytes is not None,
        notice=NOTICE_EN,
    )


@router.get("/{code}", response_model=SharedSummary)
def read_share(code: str, request: Request, shares: ShareStore = Depends(get_shares)):
    """The health worker's read-only view: the SAME summary card the patient sees."""
    rec = shares.get(code, client=_client(request), count_view=True)
    now = time.time()
    return Response(
        content=SharedSummary(
            code=rec.code,
            summary=SummaryCard.model_validate(rec.summary),
            has_audio=rec.audio is not None,
            mode=rec.mode,
            created_at=rec.created_at,
            expires_at=rec.expires_at,
            seconds_left=max(0, int(rec.expires_at - now)),
            views=rec.views,
            notice=NOTICE_EN,
        ).model_dump_json(),
        media_type="application/json",
        headers=_NO_STORE,
    )


@router.get("/{code}/audio")
def read_share_audio(code: str, request: Request, shares: ShareStore = Depends(get_shares)):
    rec = shares.get(code, client=_client(request))
    if rec.audio is None:
        raise KothaError(404, "SHARE_NO_AUDIO", "No voice clip was shared with this summary.")
    return Response(content=rec.audio, media_type=rec.audio_mime or "audio/webm", headers=_NO_STORE)


@router.delete("/{code}", status_code=204)
def revoke_share(code: str, shares: ShareStore = Depends(get_shares)):
    """Revoke immediately. Idempotent; reveals nothing about whether the code existed."""
    shares.delete(normalize_code(code))
    log.info("share_revoked code=%s", normalize_code(code)[:4])
    return Response(status_code=204, headers=_NO_STORE)
