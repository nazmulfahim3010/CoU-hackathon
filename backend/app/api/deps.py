from fastapi import Request

from app.core.session_manager import SessionManager
from app.core.share_store import ShareStore


def get_sessions(request: Request) -> SessionManager:
    return request.app.state.sessions


def get_shares(request: Request) -> ShareStore:
    return request.app.state.shares
