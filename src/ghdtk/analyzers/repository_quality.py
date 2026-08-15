"""Repository quality signals analysis (issue #29).

Per-repository presentation signals — description (presence and placeholder
detection, reusing the heuristics from #23), README presence and basic
quality, topics, license and website — aggregated into portfolio-level
metrics and evidence-backed findings.

README presence is only claimed when the collection record for that repository
completed successfully: a README that was never fetched (budget skip or API
failure) is reported as ``unknown`` so the analyzer never fabricates an
absence.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from ghdtk.analyzers.heuristics import find_placeholders
from ghdtk.analyzers.thresholds import AnalysisThresholds
from ghdtk.models.derived import (
    DimensionId,
    Finding,
    FindingSeverity,
    MetricRecord,
    SourceEntityKind,
    SourceReference,
)
from ghdtk.models.raw import CollectionStatus, ProfileSnapshot

__all__ = [
    "ReadmeState",
    "RepositoryQuality",
    "RepositoryQualitySignals",
    "assess_repository_quality",
]


class ReadmeState(StrEnum):
    """Whether a repository's README is known to exist."""

    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class RepositoryQualitySignals(BaseModel):
    """One repository's quality signals."""

    model_config = ConfigDict(frozen=True)

    full_name: str
    has_description: bool
    description_placeholder: bool
    readme: ReadmeState
    readme_chars: int | None = None
    topics_count: int
    has_license: bool
    license_name: str | None = None
    has_homepage: bool


class RepositoryQuality(BaseModel):
    """The portfolio-level repository quality assessment."""

    model_config = ConfigDict(frozen=True)

    username: str
    signals: list[RepositoryQualitySignals]
    metrics: list[MetricRecord]
    findings: list[Finding]


def _source(identifier: str, field: str) -> SourceReference:
    return SourceReference(
        entity=SourceEntityKind.REPOSITORY,
        identifier=identifier,
        field=field,
    )


def _readme_state(snapshot: ProfileSnapshot, full_name: str) -> tuple[ReadmeState, int | None]:
    readme = snapshot.readmes.get(full_name)
    if readme is not None:
        return ReadmeState.PRESENT, len(readme.decoded_content or "")
    record = next(
        (r for r in snapshot.collections if r.name == f"readme:{full_name}"),
        None,
    )
    if record is not None and record.status is CollectionStatus.SUCCESS:
        return ReadmeState.ABSENT, None
    return ReadmeState.UNKNOWN, None


def _coverage(
    signals: list[RepositoryQualitySignals],
    predicate: Callable[[RepositoryQualitySignals], bool],
) -> float:
    if not signals:
        return 0.0
    return sum(1 for signal in signals if predicate(signal)) / len(signals)


def _percent(value: float) -> str:
    return f"{round(value * 100)}%"


def assess_repository_quality(
    snapshot: ProfileSnapshot,
    *,
    thresholds: AnalysisThresholds | None = None,
) -> RepositoryQuality:
    """Assess repository quality signals for every collected repository."""
    thresholds = thresholds or AnalysisThresholds()
    repositories = snapshot.repositories or []
    signals: list[RepositoryQualitySignals] = []
    findings: list[Finding] = []

    for repo in repositories:
        full_name = repo.full_name or ""
        description = (repo.description or "").strip()
        placeholder = bool(description) and bool(find_placeholders(description))
        readme, readme_chars = _readme_state(snapshot, full_name)
        signals.append(
            RepositoryQualitySignals(
                full_name=full_name,
                has_description=bool(description),
                description_placeholder=placeholder,
                readme=readme,
                readme_chars=readme_chars,
                topics_count=len(repo.topics or []),
                has_license=repo.license is not None,
                license_name=repo.license.name if repo.license else None,
                has_homepage=bool((repo.homepage or "").strip()),
            )
        )

        if not description:
            findings.append(
                Finding(
                    id=f"repo.quality.no_description.{full_name}",
                    type="missing_information",
                    severity=FindingSeverity.LOW,
                    title=f"{full_name} has no description",
                    message="A description makes a repository discoverable in search.",
                    dimension=DimensionId.OPEN_SOURCE,
                    evidence=[_source(full_name, "description")],
                )
            )
        elif placeholder:
            findings.append(
                Finding(
                    id=f"repo.quality.placeholder_description.{full_name}",
                    type="placeholder_value",
                    severity=FindingSeverity.MEDIUM,
                    title=f"{full_name} has a placeholder description",
                    message="The description still carries placeholder text; replace it.",
                    dimension=DimensionId.OPEN_SOURCE,
                    evidence=[_source(full_name, "description")],
                )
            )

        if readme is ReadmeState.ABSENT:
            findings.append(
                Finding(
                    id=f"repo.quality.no_readme.{full_name}",
                    type="missing_information",
                    severity=FindingSeverity.LOW,
                    title=f"{full_name} has no README",
                    message="A README explains the repository's purpose and usage.",
                    dimension=DimensionId.DOCUMENTATION,
                    evidence=[_source(full_name, "readme")],
                )
            )
        elif readme is ReadmeState.PRESENT and (readme_chars or 0) < thresholds.readme_min_chars:
            findings.append(
                Finding(
                    id=f"repo.quality.thin_readme.{full_name}",
                    type="quality_issue",
                    severity=FindingSeverity.LOW,
                    title=f"{full_name} README is very short",
                    message=(
                        f"The README is only {readme_chars} characters; consider expanding "
                        f"it beyond the {thresholds.readme_min_chars}-character minimum."
                    ),
                    dimension=DimensionId.DOCUMENTATION,
                    evidence=[_source(full_name, "readme")],
                )
            )

    readme_known = [signal for signal in signals if signal.readme is not ReadmeState.UNKNOWN]
    description_coverage = _coverage(signals, lambda s: s.has_description)
    readme_coverage = _coverage(readme_known, lambda s: s.readme is ReadmeState.PRESENT)
    license_coverage = _coverage(signals, lambda s: s.has_license)
    homepage_coverage = _coverage(signals, lambda s: s.has_homepage)
    placeholder_count = sum(1 for s in signals if s.description_placeholder)
    no_description = sum(1 for s in signals if not s.has_description)
    no_readme = sum(1 for s in readme_known if s.readme is ReadmeState.ABSENT)
    avg_topics = sum(s.topics_count for s in signals) / len(signals) if signals else 0.0

    now = snapshot.collected_at
    metrics = [
        MetricRecord(
            id="portfolio.repositories.count",
            label="Repositories collected",
            value=len(signals),
            timestamp=now,
            sources=[_source(s.full_name, "name") for s in signals],
        ),
        MetricRecord(
            id="portfolio.quality.description_coverage",
            label="Repositories with a description",
            value=description_coverage,
            timestamp=now,
            sources=[_source(s.full_name, "description") for s in signals],
        ),
        MetricRecord(
            id="portfolio.quality.readme_coverage",
            label="Repositories with a README",
            value=readme_coverage,
            timestamp=now,
            sources=[_source(s.full_name, "readme") for s in readme_known],
            confidence=0.95,
        ),
        MetricRecord(
            id="portfolio.quality.license_coverage",
            label="Repositories with a license",
            value=license_coverage,
            timestamp=now,
            sources=[_source(s.full_name, "license") for s in signals],
        ),
        MetricRecord(
            id="portfolio.quality.homepage_coverage",
            label="Repositories with a website",
            value=homepage_coverage,
            timestamp=now,
            sources=[_source(s.full_name, "homepage") for s in signals],
        ),
        MetricRecord(
            id="portfolio.quality.topics.average",
            label="Average topics per repository",
            value=avg_topics,
            timestamp=now,
            sources=[_source(s.full_name, "topics") for s in signals],
        ),
        MetricRecord(
            id="portfolio.quality.placeholder_descriptions",
            label="Repositories with a placeholder description",
            value=placeholder_count,
            timestamp=now,
            sources=[_source(s.full_name, "description") for s in signals],
            confidence=0.9,
        ),
        MetricRecord(
            id="portfolio.quality.repos_no_description",
            label="Repositories without a description",
            value=no_description,
            timestamp=now,
            sources=[_source(s.full_name, "description") for s in signals],
        ),
        MetricRecord(
            id="portfolio.quality.repos_no_readme",
            label="Repositories without a README",
            value=no_readme,
            timestamp=now,
            sources=[_source(s.full_name, "readme") for s in readme_known],
        ),
    ]

    if signals:
        if description_coverage < thresholds.quality_coverage_threshold:
            findings.append(
                Finding(
                    id="portfolio.quality.low_description_coverage",
                    type="quality_issue",
                    severity=FindingSeverity.MEDIUM,
                    title="Most repositories lack a description",
                    message=(
                        f"{_percent(description_coverage)} of repositories have a description, "
                        f"below the {_percent(thresholds.quality_coverage_threshold)} threshold."
                    ),
                    dimension=DimensionId.OPEN_SOURCE,
                    evidence=[_source(s.full_name, "description") for s in signals],
                )
            )
        if readme_known and readme_coverage < thresholds.quality_coverage_threshold:
            findings.append(
                Finding(
                    id="portfolio.quality.low_readme_coverage",
                    type="quality_issue",
                    severity=FindingSeverity.MEDIUM,
                    title="Most repositories lack a README",
                    message=(
                        f"{_percent(readme_coverage)} of checked repositories have a README, "
                        f"below the {_percent(thresholds.quality_coverage_threshold)} threshold."
                    ),
                    dimension=DimensionId.DOCUMENTATION,
                    evidence=[_source(s.full_name, "readme") for s in readme_known],
                )
            )

    return RepositoryQuality(
        username=snapshot.username,
        signals=signals,
        metrics=metrics,
        findings=findings,
    )
