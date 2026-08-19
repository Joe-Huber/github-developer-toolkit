"""FastAPI application factory for the dashboard.

Creates the ASGI application that serves the API and (in production) the
React frontend as static files.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ghdtk.dashboard.routes import router

_DASHBOARD_UI_DIST = Path(__file__).resolve().parents[3] / "dashboard-ui" / "dist"


def create_app(*, cors_origins: list[str] | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Parameters
    ----------
    cors_origins:
        Allowed origins for CORS. Defaults to ``["http://localhost:5173"]``
        for Vite dev server compatibility.
    """
    app = FastAPI(
        title="ghdtk dashboard",
        description="Interactive developer profile dashboard",
        version="0.1.0",
    )

    origins = cors_origins if cors_origins is not None else ["http://localhost:5173"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    if _DASHBOARD_UI_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(_DASHBOARD_UI_DIST), html=True), name="static")

    return app
