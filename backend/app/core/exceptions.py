from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class KothaError(Exception):
    """Application error that maps to a clean HTTP response."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(KothaError)
    async def _kotha(_: Request, exc: KothaError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
