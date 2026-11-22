from fastapi import Request

from app.core.session_manager import SessionManager


def get_sessions(request: Request) -> SessionManager:
    return request.app.state.sessions
