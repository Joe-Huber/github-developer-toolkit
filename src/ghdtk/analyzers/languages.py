"""Language distribution & primary languages analysis (issue #44).

Aggregates per-repository language statistics into a portfolio-level
distribution, deriving a defensible technical profile from evidence.

Documented weighting policy:

- **Byte-based weighting.** The languages endpoint reports bytes of code per
  language per repository, so a repository with more code contributes
  proportionally more to the portfolio distribution. Each language's share is
  ``language_bytes / total_bytes`` across every repository with byte
  statistics.
- **Primary language per repository.** A repository's primary language is the
  largest language in its byte statistics. When byte statistics are absent but
  the repository metadata declares a single ``language`` (the ``Repository``
  field the API computes), that declared value is reported as the primary
  language with ``has_byte_stats=False``. A repository with neither byte
  statistics nor a declared language is counted as *unknown* and disclosed,
  never guessed.
- **Empty repositories.** A repository with byte statistics that are empty has
  no detectable code language; its primary language is reported as ``None`` and
  it is counted under ``empty_count``.
- **Missing data is disclosed.** Repositories without byte statistics do not
  distort the weighted shares; the gap is surfaced in a coverage finding.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ghdtk.analyzers.thresholds import AnalysisThresholds
from ghdtk.models.derived import (
    DimensionId,
    Finding,
    FindingSeverity,
    MetricRecord,
    SourceEntityKind,
    SourceReference,
)
from ghdtk.models.raw import ProfileSnapshot

__all__ = [
    "LanguageDistributionAnalysis",
    "LanguageShare",
    "RepositoryLanguages",
    "assess_language_distribution",
]

_UNAVAILABLE = "unavailable"


def _round(value: float, digits: int = 2) -> float:
    return round(value, digits)


def _source(identifier: str, field: str) -> SourceReference:
    return SourceReference(
        entity=SourceEntityKind.REPOSITORY,
        identifier=identifier,
        field=field,
    )


class RepositoryLanguages(BaseModel):
    """One repository's language signals."""

    model_config = ConfigDict(frozen=True)

    full_name: str
    primary: str | None = None
    bytes_total: int | None = None
    has_byte_stats: bool = False
    declared: str | None = None


class LanguageShare(BaseModel):
    """One language's portfolio-level weight."""

    model_config = ConfigDict(frozen=True)

    language: str
    bytes: int
    share: float


class LanguageDistributionAnalysis(BaseModel):
    """The language distribution assessment."""

    model_config = ConfigDict(frozen=True)

    username: str
    repositories: list[RepositoryLanguages]
    distribution: list[LanguageShare]
    dominant_language: str | None = None
    dominant_share: float | None = None
    distinct_languages: int = 0
    total_bytes: int = 0
    repos_with_stats: int = 0
    declared_only_count: int = 0
    unknown_count: int = 0
    empty_count: int = 0
    metrics: list[MetricRecord]
    findings: list[Finding]


def assess_language_distribution(
    snapshot: ProfileSnapshot,
    *,
    thresholds: AnalysisThresholds | None = None,
) -> LanguageDistributionAnalysis:
    """Assess the portfolio's language distribution and primary languages."""
    thresholds = thresholds or AnalysisThresholds()
    now_ts = snapshot.collected_at
    repositories = snapshot.repositories or []
    language_stats = snapshot.languages or {}

    repo_rows: list[RepositoryLanguages] = []
    language_bytes: dict[str, int] = {}
    language_repos: dict[str, set[str]] = {}
    repos_with_stats = 0
    declared_only_count = 0
    unknown_count = 0
    empty_count = 0

    for repo in repositories:
        full_name = repo.full_name
        if full_name is None:
            continue
        stats = language_stats.get(full_name)
        declared = repo.language
        if stats is not None:
            languages = stats.root
            repo_bytes = sum(languages.values())
            primary = (
                max(languages, key=lambda language: languages[language]) if languages else None
            )
            repo_rows.append(
                RepositoryLanguages(
                    full_name=full_name,
                    primary=primary,
                    bytes_total=repo_bytes,
                    has_byte_stats=True,
                    declared=declared,
                )
            )
            repos_with_stats += 1
            if repo_bytes == 0:
                empty_count += 1
            for language, byte_count in languages.items():
                language_bytes[language] = language_bytes.get(language, 0) + byte_count
                language_repos.setdefault(language, set()).add(full_name)
        elif declared:
            repo_rows.append(
                RepositoryLanguages(
                    full_name=full_name,
                    primary=declared,
                    has_byte_stats=False,
                    declared=declared,
                )
            )
            declared_only_count += 1
        else:
            repo_rows.append(RepositoryLanguages(full_name=full_name, has_byte_stats=False))
            unknown_count += 1

    total_bytes = sum(language_bytes.values())
    distribution = sorted(
        (
            LanguageShare(
                language=language,
                bytes=byte_count,
                share=_round(byte_count / total_bytes) if total_bytes > 0 else 0.0,
            )
            for language, byte_count in language_bytes.items()
        ),
        key=lambda entry: entry.bytes,
        reverse=True,
    )
    dominant = distribution[0] if distribution else None
    dominant_language = dominant.language if dominant else None
    dominant_share = dominant.share if dominant else None
    distinct_languages = len(distribution)

    repo_sources = [_source(row.full_name, "language") for row in repo_rows]
    findings: list[Finding] = []

    if not repo_rows:
        findings.append(
            Finding(
                id="languages.no_repositories",
                type="informational",
                severity=FindingSeverity.INFO,
                title="No repositories for language analysis",
                message=(
                    "The snapshot contains no repositories; the language distribution is empty."
                ),
                dimension=DimensionId.CODE_QUALITY,
                evidence=[],
            )
        )
    elif total_bytes == 0 and declared_only_count == 0 and unknown_count == 0:
        findings.append(
            Finding(
                id="languages.no_data",
                type="informational",
                severity=FindingSeverity.INFO,
                title="No language data collected",
                message=(
                    "The portfolio repositories carry no language bytes and no "
                    "declared languages; the language distribution is empty."
                ),
                dimension=DimensionId.CODE_QUALITY,
                evidence=repo_sources,
            )
        )
    else:
        if declared_only_count or unknown_count:
            findings.append(
                Finding(
                    id="languages.coverage_gap",
                    type="informational",
                    severity=FindingSeverity.INFO,
                    title="Some repositories lack byte language statistics",
                    message=(
                        f"{declared_only_count} repository(ies) only carry a "
                        "declared primary language and "
                        f"{unknown_count} repository(ies) carry no language data "
                        "at all; the weighted distribution covers only the "
                        "repositories with byte statistics."
                    ),
                    dimension=DimensionId.CODE_QUALITY,
                    evidence=repo_sources,
                )
            )
        if empty_count:
            findings.append(
                Finding(
                    id="languages.empty_repositories",
                    type="informational",
                    severity=FindingSeverity.INFO,
                    title="Some repositories contain no detectable code",
                    message=(
                        f"{empty_count} repository(ies) have empty language "
                        "statistics and no primary language."
                    ),
                    dimension=DimensionId.CODE_QUALITY,
                    evidence=[
                        _source(row.full_name, "language")
                        for row in repo_rows
                        if row.has_byte_stats and row.bytes_total == 0
                    ],
                )
            )
        if dominant is not None and dominant.share >= thresholds.language_concentration_threshold:
            findings.append(
                Finding(
                    id="languages.concentrated",
                    type="quality_issue",
                    severity=FindingSeverity.LOW,
                    title="Portfolio is concentrated on one language",
                    message=(
                        f"{dominant_language} holds {dominant.share:.0%} of the "
                        "portfolio's language bytes, at or above the "
                        f"{thresholds.language_concentration_threshold:.0%} "
                        "concentration threshold."
                    ),
                    dimension=DimensionId.CODE_QUALITY,
                    evidence=[
                        _source(name, "language")
                        for name in sorted(language_repos.get(dominant_language or "", set()))
                    ],
                )
            )
        if distinct_languages >= thresholds.language_distinct_threshold:
            findings.append(
                Finding(
                    id="languages.polyglot",
                    type="standout",
                    severity=FindingSeverity.INFO,
                    title="Portfolio spans many languages",
                    message=(
                        f"The portfolio covers {distinct_languages} distinct "
                        f"languages, at or above the "
                        f"{thresholds.language_distinct_threshold}-language "
                        "threshold."
                    ),
                    dimension=DimensionId.CODE_QUALITY,
                    evidence=repo_sources,
                )
            )

    metrics = [
        MetricRecord(
            id="languages.repos.total",
            label="Repositories analyzed",
            value=len(repo_rows),
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="languages.repos.with_byte_stats",
            label="Repositories with byte statistics",
            value=repos_with_stats,
            timestamp=now_ts,
            sources=[_source(row.full_name, "language") for row in repo_rows if row.has_byte_stats],
        ),
        MetricRecord(
            id="languages.repos.declared_only",
            label="Repositories with declared language only",
            value=declared_only_count,
            timestamp=now_ts,
            sources=[
                _source(row.full_name, "language")
                for row in repo_rows
                if not row.has_byte_stats and row.declared is not None
            ],
        ),
        MetricRecord(
            id="languages.repos.unknown",
            label="Repositories with no language data",
            value=unknown_count,
            timestamp=now_ts,
            sources=[
                _source(row.full_name, "language")
                for row in repo_rows
                if not row.has_byte_stats and row.declared is None
            ],
        ),
        MetricRecord(
            id="languages.repos.empty",
            label="Repositories with no detectable code",
            value=empty_count,
            timestamp=now_ts,
            sources=[
                _source(row.full_name, "language")
                for row in repo_rows
                if row.has_byte_stats and row.bytes_total == 0
            ],
        ),
        MetricRecord(
            id="languages.total_bytes",
            label="Total language bytes",
            value=total_bytes,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="languages.distinct_languages",
            label="Distinct languages",
            value=distinct_languages,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="languages.dominant_language",
            label="Dominant language",
            value=dominant_language if dominant_language is not None else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
        MetricRecord(
            id="languages.dominant_share",
            label="Dominant language share",
            value=_round(dominant_share) if dominant_share is not None else _UNAVAILABLE,
            timestamp=now_ts,
            sources=repo_sources,
        ),
    ]
    for entry in distribution:
        entry_sources = [
            _source(name, "language") for name in sorted(language_repos.get(entry.language, set()))
        ]
        metrics.append(
            MetricRecord(
                id=f"languages.share.{entry.language}",
                label=f"Share of {entry.language}",
                value=entry.share,
                timestamp=now_ts,
                sources=entry_sources,
            )
        )
        metrics.append(
            MetricRecord(
                id=f"languages.bytes.{entry.language}",
                label=f"Bytes of {entry.language}",
                value=entry.bytes,
                timestamp=now_ts,
                sources=entry_sources,
            )
        )
    for row in repo_rows:
        metrics.append(
            MetricRecord(
                id=f"languages.primary.{row.full_name}",
                label=f"Primary language of {row.full_name}",
                value=row.primary if row.primary is not None else _UNAVAILABLE,
                timestamp=now_ts,
                sources=[_source(row.full_name, "language")],
            )
        )
        metrics.append(
            MetricRecord(
                id=f"languages.repo_bytes.{row.full_name}",
                label=f"Language bytes in {row.full_name}",
                value=row.bytes_total if row.bytes_total is not None else _UNAVAILABLE,
                timestamp=now_ts,
                sources=[_source(row.full_name, "language")],
            )
        )

    return LanguageDistributionAnalysis(
        username=snapshot.username,
        repositories=repo_rows,
        distribution=distribution,
        dominant_language=dominant_language,
        dominant_share=_round(dominant_share) if dominant_share is not None else None,
        distinct_languages=distinct_languages,
        total_bytes=total_bytes,
        repos_with_stats=repos_with_stats,
        declared_only_count=declared_only_count,
        unknown_count=unknown_count,
        empty_count=empty_count,
        metrics=metrics,
        findings=findings,
    )
