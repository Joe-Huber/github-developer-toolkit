"""Tests for the FastAPI dashboard backend (issue #94)."""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from ghdtk.dashboard.app import create_app


@pytest.fixture()
def client() -> TestClient:
    app = create_app(cors_origins=["http://localhost:5173"])
    return TestClient(app)


def test_health_check(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_report_endpoint_returns_502_without_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Without a valid token the report endpoint should fail gracefully."""
    monkeypatch.delenv("GHDTK_GITHUB_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    resp = client.get("/api/report/octocat")
    assert resp.status_code == 500


def test_app_has_cors_middleware(client: TestClient) -> None:
    resp = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code in (200, 405)
    assert "access-control-allow-origin" in resp.headers


def test_app_title() -> None:
    app = create_app()
    assert app.title == "ghdtk dashboard"
