"""Technology diversity & dominant-area analysis (issue #45).

Measures how a profile's technical profile spreads across technology domains
(web, data, mobile, infrastructure, backend) using only language and topic
evidence, and detects specialization.

Documented methodology:

- **Domain mapping is documented and configurable.** Every technology name — a
  language reported in the byte statistics or a repository topic — maps to
  exactly one domain in :data:`DEFAULT_DOMAIN_MAP`. The default mapping is
  deliberately opinionated (e.g. ``Python`` is mapped to the ``data`` domain,
  ``Kotlin`` to ``mobile``) and can be overridden per call via ``domain_map``.
- **Byte-weighted domain shares.** Domains are weighted from the same
  per-repository language byte statistics used by the language distribution
  analysis (issue #44). A domain's share is its bytes divided by the total
  bytes mapped to known domains. Languages not present in the mapping never
  silently inflate a domain: they accumulate into ``unmapped_bytes`` and are
  disclosed through ``unmapped_share``, never guessed.
- **Simpson diversity index.** Diversity is the Simpson index
  ``1 - sum(p_i^2)`` over the mapped domain shares: ``0`` means a single
  domain, approaching ``1`` means the mapped bytes spread evenly. The index is
  only reported when at least one domain has byte evidence.
- **Topics corroborate, they do not re-weight.** Repository topics that match
  the mapping are reported as per-domain presence counts and appear in finding
  evidence, but they do not change the byte-weighted index. A profile whose
  only evidence is topics (no language bytes) reports no weighted index and an
  informational finding explains why.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from ghdtk.analyzers.thresholds import AnalysisThresholds
from ghdtk.models.derived import (
    DimensionId,
    Finding,
    FindingSeverity,
    MetricAvailability,
    MetricRecord,
    SourceEntityKind,
    SourceReference,
)
from ghdtk.models.raw import ProfileSnapshot

__all__ = [
    "DEFAULT_DOMAIN_MAP",
    "DomainShare",
    "TechnologyDiversityAnalysis",
    "assess_technology_diversity",
]

DEFAULT_DOMAIN_MAP: dict[str, str] = {
    # Web
    "JavaScript": "web",
    "TypeScript": "web",
    "HTML": "web",
    "CSS": "web",
    "SCSS": "web",
    "Sass": "web",
    "Less": "web",
    "Ruby": "web",
    "PHP": "web",
    "Vue": "web",
    "Astro": "web",
    "React": "web",
    "Next.js": "web",
    "Nuxt": "web",
    "Angular": "web",
    "Svelte": "web",
    "Vite": "web",
    "Tailwind CSS": "web",
    "webpack": "web",
    "Django": "web",
    "Flask": "web",
    "Rails": "web",
    "Laravel": "web",
    # Data
    "Python": "data",
    "R": "data",
    "SQL": "data",
    "Jupyter Notebook": "data",
    "Julia": "data",
    "pandas": "data",
    "NumPy": "data",
    "dbt": "data",
    "Airflow": "data",
    "Spark": "data",
    "Kafka": "data",
    "Elasticsearch": "data",
    "MongoDB": "data",
    "PostgreSQL": "data",
    "MySQL": "data",
    "sqlite": "data",
    "Snowflake": "data",
    # Mobile
    "Kotlin": "mobile",
    "Swift": "mobile",
    "Objective-C": "mobile",
    "Dart": "mobile",
    "Flutter": "mobile",
    "React Native": "mobile",
    "Android": "mobile",
    "iOS": "mobile",
    "KMP": "mobile",
    # Infrastructure
    "Go": "infrastructure",
    "Rust": "infrastructure",
    "C": "infrastructure",
    "C++": "infrastructure",
    "Zig": "infrastructure",
    "Shell": "infrastructure",
    "PowerShell": "infrastructure",
    "Dockerfile": "infrastructure",
    "Makefile": "infrastructure",
    "CMake": "infrastructure",
    "Nix": "infrastructure",
    "Assembly": "infrastructure",
    "Docker": "infrastructure",
    "Kubernetes": "infrastructure",
    "Terraform": "infrastructure",
    "Ansible": "infrastructure",
    "Helm": "infrastructure",
    "AWS": "infrastructure",
    "GCP": "infrastructure",
    "Azure": "infrastructure",
    # Backend
    "Java": "backend",
    "C#": "backend",
    "Scala": "backend",
    "Elixir": "backend",
    "Erlang": "backend",
    "Clojure": "backend",
    "Haskell": "backend",
    "F#": "backend",
    "Perl": "backend",
    "GraphQL": "backend",
    "gRPC": "backend",
    "Redis": "backend",
}


def _round(value: float, digits: int = 2) -> float:
    return round(value, digits)


def _source(identifier: str, field: str) -> SourceReference:
    return SourceReference(
        entity=SourceEntityKind.REPOSITORY,
        identifier=identifier,
        field=field,
    )


class DomainShare(BaseModel):
    """One technology domain's weighted share and contributing repositories."""

    model_config = ConfigDict(frozen=True)

    domain: str
    bytes: int
    share: float
    language_repositories: list[str]
    topic_repositories: list[str]


class TechnologyDiversityAnalysis(BaseModel):
    """The technology diversity & dominant-area assessment."""

    model_config = ConfigDict(frozen=True)

    username: str
    domain_shares: list[DomainShare]
    simpson_index: float | None = None
    top_domain: str | None = None
    top_domain_share: float | None = None
    domains_count: int = 0
    total_bytes: int = 0
    mapped_bytes: int = 0
    unmapped_bytes: int = 0
    mapped_share: float | None = None
    unmapped_share: float | None = None
    topic_presence: dict[str, int] = {}
    metrics: list[MetricRecord]
    findings: list[Finding]


def assess_technology_diversity(
    snapshot: ProfileSnapshot,
    *,
    thresholds: AnalysisThresholds | None = None,
    domain_map: Mapping[str, str] | None = None,
) -> TechnologyDiversityAnalysis:
    """Assess technology diversity and specialization from language/topic evidence."""
    thresholds = thresholds or AnalysisThresholds()
    mapping = DEFAULT_DOMAIN_MAP if domain_map is None else domain_map
    # Language names and repository topics differ in casing (GitHub reports
    # "Python" as a language but "python" as a topic), so lookups are
    # case-insensitive.
    lookup = {name.casefold(): domain for name, domain in mapping.items()}
    now_ts = snapshot.collected_at
    repositories = snapshot.repositories or []
    language_stats = snapshot.languages or {}

    domain_bytes: dict[str, int] = {}
    domain_language_repos: dict[str, set[str]] = {}
    domain_topic_repos: dict[str, set[str]] = {}
    topic_presence: dict[str, int] = {}
    unmapped_bytes = 0
    unmapped_repos: set[str] = set()
    topic_repos: set[str] = set()
    total_bytes = 0

    for repo in repositories:
        full_name = repo.full_name
        if full_name is None:
            continue
        stats = language_stats.get(full_name)
        if stats is not None:
            languages = stats.root
            for language, byte_count in languages.items():
                total_bytes += byte_count
                domain = lookup.get(language.casefold())
                if domain is None:
                    unmapped_bytes += byte_count
                    unmapped_repos.add(full_name)
                else:
                    domain_bytes[domain] = domain_bytes.get(domain, 0) + byte_count
                    domain_language_repos.setdefault(domain, set()).add(full_name)
        for topic in repo.topics or []:
            domain = lookup.get(topic.casefold())
            if domain is None:
                continue
            topic_presence[domain] = topic_presence.get(domain, 0) + 1
            domain_topic_repos.setdefault(domain, set()).add(full_name)
            topic_repos.add(full_name)

    mapped_bytes = sum(domain_bytes.values())
    mapped_share = mapped_bytes / total_bytes if total_bytes > 0 else None
    unmapped_share = unmapped_bytes / total_bytes if total_bytes > 0 else None

    domain_shares: list[DomainShare] = []
    simpson_index: float | None = None
    if mapped_bytes > 0:
        domain_shares = sorted(
            (
                DomainShare(
                    domain=domain,
                    bytes=byte_count,
                    share=_round(byte_count / mapped_bytes),
                    language_repositories=sorted(domain_language_repos.get(domain, set())),
                    topic_repositories=sorted(domain_topic_repos.get(domain, set())),
                )
                for domain, byte_count in domain_bytes.items()
            ),
            key=lambda entry: entry.bytes,
            reverse=True,
        )
        shares = [entry.share for entry in domain_shares]
        simpson_index = _round(1.0 - sum(share * share for share in shares))

    top = domain_shares[0] if domain_shares else None
    top_domain = top.domain if top else None
    top_domain_share = top.share if top else None
    domains_count = len(domain_shares)

    all_repo_sources = [
        _source(repo.full_name or "", "language") for repo in repositories if repo.full_name
    ]
    topic_sources = [_source(name, "topics") for name in sorted(topic_repos)]
    findings: list[Finding] = []

    if total_bytes == 0 and not topic_repos:
        findings.append(
            Finding(
                id="tech.no_evidence",
                type="informational",
                severity=FindingSeverity.INFO,
                title="No technology evidence collected",
                message=(
                    "No language bytes or topics were collected, so technology "
                    "diversity and specialization cannot be assessed."
                ),
                dimension=DimensionId.CODE_QUALITY,
                evidence=all_repo_sources,
            )
        )
    elif total_bytes == 0:
        findings.append(
            Finding(
                id="tech.no_byte_evidence",
                type="informational",
                severity=FindingSeverity.INFO,
                title="Only topic evidence is available",
                message=(
                    "Topics were collected but no language bytes, so the "
                    "byte-weighted diversity index is not reported; topic "
                    "presence is still surfaced as evidence."
                ),
                dimension=DimensionId.CODE_QUALITY,
                evidence=topic_sources,
            )
        )
    elif mapped_bytes == 0:
        findings.append(
            Finding(
                id="tech.no_mapped_domains",
                type="informational",
                severity=FindingSeverity.INFO,
                title="No languages map to a known technology domain",
                message=(
                    "None of the collected languages appear in the domain "
                    "mapping; technology diversity is not reported. Adjust the "
                    "domain map to cover these languages."
                ),
                dimension=DimensionId.CODE_QUALITY,
                evidence=all_repo_sources,
            )
        )
    else:
        if (
            mapped_share is not None
            and mapped_share < thresholds.technology_mapping_coverage_threshold
        ):
            findings.append(
                Finding(
                    id="tech.low_mapping_coverage",
                    type="informational",
                    severity=FindingSeverity.INFO,
                    title="Most language bytes are not mapped to a domain",
                    message=(
                        f"{unmapped_share:.0%} of the portfolio's language bytes "
                        "do not map to a known technology domain; domain shares "
                        "cover only the mapped remainder."
                    ),
                    dimension=DimensionId.CODE_QUALITY,
                    evidence=[_source(name, "language") for name in sorted(unmapped_repos)],
                )
            )
        if top is not None and top.share >= thresholds.technology_specialization_threshold:
            findings.append(
                Finding(
                    id="tech.specialized",
                    type="standout",
                    severity=FindingSeverity.INFO,
                    title=f"Profile is specialized in {top_domain}",
                    message=(
                        f"The {top_domain} domain holds {top.share:.0%} of the "
                        "mapped language bytes, at or above the "
                        f"{thresholds.technology_specialization_threshold:.0%} "
                        "specialization threshold."
                    ),
                    dimension=DimensionId.CODE_QUALITY,
                    evidence=[_source(name, "language") for name in top.language_repositories]
                    + [_source(name, "topics") for name in top.topic_repositories],
                )
            )
        if simpson_index is not None and simpson_index >= thresholds.technology_diversity_threshold:
            findings.append(
                Finding(
                    id="tech.diverse",
                    type="standout",
                    severity=FindingSeverity.INFO,
                    title="Portfolio spans diverse technology domains",
                    message=(
                        f"The {domains_count} detected technology domains reach a "
                        f"Simpson diversity index of {simpson_index:.2f}, at or "
                        "above the "
                        f"{thresholds.technology_diversity_threshold:.2f} "
                        "diversity threshold."
                    ),
                    dimension=DimensionId.CODE_QUALITY,
                    evidence=all_repo_sources + topic_sources,
                )
            )

    metrics = [
        MetricRecord(
            id="tech.total_bytes",
            label="Total language bytes",
            value=total_bytes,
            timestamp=now_ts,
            sources=all_repo_sources,
        ),
        MetricRecord(
            id="tech.mapped_bytes",
            label="Bytes mapped to a domain",
            value=mapped_bytes,
            timestamp=now_ts,
            sources=all_repo_sources,
        ),
        MetricRecord(
            id="tech.unmapped_bytes",
            label="Bytes not mapped to a domain",
            value=unmapped_bytes,
            timestamp=now_ts,
            sources=[_source(name, "language") for name in sorted(unmapped_repos)],
        ),
        MetricRecord(
            id="tech.mapped_share",
            label="Share of bytes mapped to a domain",
            value=_round(mapped_share) if mapped_share is not None else None,
            availability=(
                MetricAvailability.AVAILABLE
                if mapped_share is not None
                else MetricAvailability.UNAVAILABLE
            ),
            timestamp=now_ts,
            sources=all_repo_sources,
        ),
        MetricRecord(
            id="tech.unmapped_share",
            label="Share of bytes not mapped to a domain",
            value=_round(unmapped_share) if unmapped_share is not None else None,
            availability=(
                MetricAvailability.AVAILABLE
                if unmapped_share is not None
                else MetricAvailability.UNAVAILABLE
            ),
            timestamp=now_ts,
            sources=[_source(name, "language") for name in sorted(unmapped_repos)],
        ),
        MetricRecord(
            id="tech.domains_count",
            label="Technology domains detected",
            value=domains_count,
            timestamp=now_ts,
            sources=all_repo_sources,
        ),
        MetricRecord(
            id="tech.simpson_index",
            label="Technology diversity (Simpson index)",
            value=_round(simpson_index) if simpson_index is not None else None,
            availability=(
                MetricAvailability.AVAILABLE
                if simpson_index is not None
                else MetricAvailability.UNAVAILABLE
            ),
            timestamp=now_ts,
            sources=all_repo_sources,
        ),
        MetricRecord(
            id="tech.top_domain",
            label="Dominant technology domain",
            value=top_domain,
            availability=(
                MetricAvailability.AVAILABLE
                if top_domain is not None
                else MetricAvailability.UNAVAILABLE
            ),
            timestamp=now_ts,
            sources=all_repo_sources,
        ),
        MetricRecord(
            id="tech.top_domain_share",
            label="Dominant domain share",
            value=_round(top_domain_share) if top_domain_share is not None else None,
            availability=(
                MetricAvailability.AVAILABLE
                if top_domain_share is not None
                else MetricAvailability.UNAVAILABLE
            ),
            timestamp=now_ts,
            sources=all_repo_sources,
        ),
    ]
    for entry in domain_shares:
        entry_sources = [_source(name, "language") for name in entry.language_repositories] + [
            _source(name, "topics") for name in entry.topic_repositories
        ]
        metrics.append(
            MetricRecord(
                id=f"tech.domain_share.{entry.domain}",
                label=f"Share of {entry.domain} domain",
                value=entry.share,
                timestamp=now_ts,
                sources=entry_sources,
            )
        )
        metrics.append(
            MetricRecord(
                id=f"tech.domain_bytes.{entry.domain}",
                label=f"Bytes in {entry.domain} domain",
                value=entry.bytes,
                timestamp=now_ts,
                sources=entry_sources,
            )
        )
    for domain, count in sorted(topic_presence.items()):
        metrics.append(
            MetricRecord(
                id=f"tech.topics.{domain}",
                label=f"{domain} topic presence",
                value=count,
                timestamp=now_ts,
                sources=[
                    _source(name, "topics")
                    for name in sorted(domain_topic_repos.get(domain, set()))
                ],
            )
        )

    return TechnologyDiversityAnalysis(
        username=snapshot.username,
        domain_shares=domain_shares,
        simpson_index=_round(simpson_index) if simpson_index is not None else None,
        top_domain=top_domain,
        top_domain_share=_round(top_domain_share) if top_domain_share is not None else None,
        domains_count=domains_count,
        total_bytes=total_bytes,
        mapped_bytes=mapped_bytes,
        unmapped_bytes=unmapped_bytes,
        mapped_share=_round(mapped_share) if mapped_share is not None else None,
        unmapped_share=_round(unmapped_share) if unmapped_share is not None else None,
        topic_presence=topic_presence,
        metrics=metrics,
        findings=findings,
    )
