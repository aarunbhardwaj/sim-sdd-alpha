"""FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from handoff.routes import router
from handoff.store import DEFAULT_DB


def create_app(db_path: Path | str = DEFAULT_DB) -> FastAPI:
    app = FastAPI(title="Shift Handoff Log", version="0.1.0")
    app.state.db_path = Path(db_path)
    app.include_router(router)

    @app.exception_handler(RequestValidationError)
    async def invalid_payload(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "invalid handoff payload"})

    return app


app = create_app()
