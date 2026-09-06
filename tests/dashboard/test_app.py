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


def test_report_endpoint_returns_400_without_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Without a valid token the report endpoint should fail with a handled error."""
    monkeypatch.delenv("GHDTK_GITHUB_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    resp = client.get("/api/report/octocat")
    assert resp.status_code == 400
    assert "GHDTK_GITHUB_TOKEN" in resp.json()["detail"]


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


def test_report_endpoint_collects_readme_with_open_client(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issue #171: verify collect_profile_readme receives an active (unclosed) client."""
    from datetime import UTC, datetime

    from ghdtk.models.raw import ProfileReadme, ProfileReadmeStatus, ProfileSnapshot, User

    monkeypatch.setenv("GHDTK_GITHUB_TOKEN", "test-token")

    fake_snapshot = ProfileSnapshot(
        username="octocat",
        collected_at=datetime.now(UTC),
        user=User(login="octocat"),
    )
    fake_readme = ProfileReadme(
        username="octocat",
        status=ProfileReadmeStatus.PRESENT,
        content="# Hello World",
        repository="octocat/octocat",
    )

    client_state: dict[str, bool] = {}

    def mock_collect_profile(api_client: Any, username: str, **kwargs: Any) -> ProfileSnapshot:
        assert not api_client._client.is_closed
        return fake_snapshot

    def mock_collect_profile_readme(api_client: Any, username: str, **kwargs: Any) -> ProfileReadme:
        client_state["is_closed"] = api_client._client.is_closed
        return fake_readme

    monkeypatch.setattr("ghdtk.collectors.orchestrator.collect_profile", mock_collect_profile)
    monkeypatch.setattr(
        "ghdtk.collectors.collectors.collect_profile_readme", mock_collect_profile_readme
    )

    resp = client.get("/api/report/octocat")
    assert resp.status_code == 200
    data = resp.json()
    assert data["profile"]["username"] == "octocat"
    assert client_state.get("is_closed") is False
