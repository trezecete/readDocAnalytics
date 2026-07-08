from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.web.routes import router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Read Doc Analytics",
        version="0.1.0",
        description="Prototype for reviewing AI project proposals from Google Docs.",
    )
    app.state.settings = settings
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(router)
    return app


app = create_app()

