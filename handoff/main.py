"""FastAPI application factory."""

from fastapi import FastAPI

from handoff.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="Shift Handoff Log", version="0.1.0")
    app.include_router(router)
    return app


app = create_app()
