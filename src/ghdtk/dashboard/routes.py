"""API routes for the dashboard.

Endpoints serve report data produced by the analysis pipeline. The report is
generated on-demand for a given username and returned as JSON.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from ghdtk.dashboard.schemas import HealthResponse, ReportResponse

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)  # type: ignore[untyped-decorator]
async def health_check() -> HealthResponse:
    return HealthResponse()


@router.get("/report/{username}", response_model=ReportResponse)  # type: ignore[untyped-decorator]
async def get_report(username: str) -> ReportResponse:
    """Run the full analysis pipeline and return the report as JSON."""
    from ghdtk.api.client import GitHubClient
    from ghdtk.collectors.collectors import collect_profile_readme
    from ghdtk.collectors.orchestrator import collect_profile
    from ghdtk.config import load_settings
    from ghdtk.report.assemble import ReportAssembler

    try:
        settings = load_settings()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Configuration error: {exc}") from exc

    client = GitHubClient.from_settings(settings)
    try:
        with client:
            snapshot = collect_profile(
                client,
                username,
                max_requests=settings.collection_max_requests,
                max_workers=settings.collection_max_workers,
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Collection failed: {exc}") from exc

    try:
        with client:
            readme = collect_profile_readme(client, username, repositories=snapshot.repositories)
    except Exception:
        readme = None

    now = datetime.now(UTC)
    report = ReportAssembler().assemble(
        username=username,
        snapshot=snapshot,
        now=now,
        profile_readme=readme,
    )

    return ReportResponse.from_report(report)
