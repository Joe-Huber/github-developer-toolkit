"""Profile summary assembly (issues #224, #225).

Builds the two blocks the dashboard profile page renders — identity and top
stats — straight from an already-collected raw snapshot. No new GitHub data is
fetched; every headline stat is a derived value carrying the raw sources that
produced it and an honest availability marker (see #64).
"""

from __future__ import annotations

from datetime import UTC, datetime

from ghdtk.models.derived.metric import MetricAvailability, MetricRecord
from ghdtk.models.derived.profile import (
    ProfileIdentity,
    ProfileTopStats,
    TopLanguage,
    TopRepository,
)
from ghdtk.models.derived.provenance import SourceEntityKind, SourceReference
from ghdtk.models.raw import ProfileSnapshot, User

__all__ = ["build_profile_identity", "build_profile_top_stats"]


def _now(value: datetime | None) -> datetime:
    now = value or datetime.now(UTC)
    if now.tzinfo is None:
        return now.replace(tzinfo=UTC)
    return now.astimezone(UTC)


def _profile_source(username: str) -> SourceReference:
    return SourceReference(entity=SourceEntityKind.PROFILE, identifier=username)


def _user_source(username: str, field: str) -> SourceReference:
    return SourceReference(entity=SourceEntityKind.USER, identifier=username, field=field)


def build_profile_identity(user: User | None) -> ProfileIdentity | None:
    """Forward the raw ``User`` snapshot as a typed identity block.

    Returns ``None`` when no ``User`` snapshot was collected so consumers treat
    an unknown profile explicitly instead of showing fabricated values.
    """
    if user is None:
        return None
    return ProfileIdentity(
        username=user.login,
        name=user.name,
        avatar_url=user.avatar_url,
        html_url=user.html_url,
        bio=user.bio,
        company=user.company,
        blog=user.blog,
        location=user.location,
        email=user.email,
        twitter_username=user.twitter_username,
        hireable=user.hireable,
        public_repos=user.public_repos,
        public_gists=user.public_gists,
        followers=user.followers,
        following=user.following,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _aggregate_languages(
    snapshot: ProfileSnapshot,
    *,
    limit: int,
) -> tuple[list[TopLanguage], int]:
    byte_counts: dict[str, int] = {}
    for stats in snapshot.languages.values():
        for language, byte_count in stats.root.items():
            byte_counts[language] = byte_counts.get(language, 0) + byte_count
    total_bytes = sum(byte_counts.values())
    ranked = sorted(byte_counts.items(), key=lambda item: item[1], reverse=True)
    languages = [
        TopLanguage(
            language=language,
            bytes=byte_count,
            share=byte_count / total_bytes if total_bytes else 0.0,
        )
        for language, byte_count in ranked[:limit]
    ]
    return languages, total_bytes


def build_profile_top_stats(
    username: str,
    snapshot: ProfileSnapshot,
    *,
    now: datetime | None = None,
    top_repositories_limit: int = 5,
    top_languages_limit: int = 5,
) -> ProfileTopStats:
    """Compute the headline profile statistics from an existing snapshot."""
    now = _now(now)
    user = snapshot.user
    owned = [repo for repo in (snapshot.repositories or []) if not bool(repo.fork)]

    total_stars = sum((repo.stargazers_count or 0) for repo in owned)
    total_forks = sum((repo.forks_count or repo.forks or 0) for repo in owned)

    repository_sources = [
        SourceReference(
            entity=SourceEntityKind.REPOSITORY,
            identifier=repo.full_name or repo.name or username,
        )
        for repo in owned
    ]

    metrics: list[MetricRecord] = [
        MetricRecord(
            id="top_stats.repositories",
            label="Public repositories",
            value=len(owned),
            timestamp=now,
            sources=repository_sources,
        ),
        MetricRecord(
            id="top_stats.stars",
            label="Total stars",
            value=total_stars,
            timestamp=now,
            sources=repository_sources,
        ),
        MetricRecord(
            id="top_stats.forks",
            label="Total forks",
            value=total_forks,
            timestamp=now,
            sources=repository_sources,
        ),
    ]

    if user is not None:
        metrics.extend(
            [
                MetricRecord(
                    id="top_stats.followers",
                    label="Followers",
                    value=user.followers,
                    timestamp=now,
                    sources=[_user_source(username, "followers")],
                ),
                MetricRecord(
                    id="top_stats.following",
                    label="Following",
                    value=user.following,
                    timestamp=now,
                    sources=[_user_source(username, "following")],
                ),
                MetricRecord(
                    id="top_stats.public_gists",
                    label="Public gists",
                    value=user.public_gists,
                    timestamp=now,
                    sources=[_user_source(username, "public_gists")],
                ),
            ]
        )

    total_commits = sum(len(commits) for commits in snapshot.commits.values())
    metrics.append(
        MetricRecord(
            id="top_stats.commits",
            label="Commits collected",
            value=total_commits,
            timestamp=now,
            availability=MetricAvailability.PARTIAL,
            sources=[_profile_source(username)],
        )
    )

    metrics.append(
        MetricRecord(
            id="top_stats.pull_requests",
            label="Pull requests",
            value=len(snapshot.search_pull_requests),
            timestamp=now,
            availability=MetricAvailability.PARTIAL,
            sources=[_profile_source(username)],
        )
    )
    metrics.append(
        MetricRecord(
            id="top_stats.issues",
            label="Issues",
            value=len(snapshot.search_issues),
            timestamp=now,
            availability=MetricAvailability.PARTIAL,
            sources=[_profile_source(username)],
        )
    )

    if snapshot.contribution_calendar is not None:
        metrics.append(
            MetricRecord(
                id="top_stats.contributions",
                label="Contributions (past year)",
                value=snapshot.contribution_calendar.total_contributions,
                timestamp=now,
                availability=MetricAvailability.PARTIAL,
                sources=[
                    SourceReference(
                        entity=SourceEntityKind.CONTRIBUTION_CALENDAR,
                        identifier=username,
                        field="total_contributions",
                    )
                ],
            )
        )

    top_repositories = sorted(owned, key=lambda repo: repo.stargazers_count or 0, reverse=True)[
        :top_repositories_limit
    ]

    top_languages, _ = _aggregate_languages(snapshot, limit=top_languages_limit)

    availability = (
        MetricAvailability.PARTIAL if snapshot.is_partial else MetricAvailability.AVAILABLE
    )

    return ProfileTopStats(
        username=username,
        metrics=metrics,
        top_repositories=[
            TopRepository(
                name=repo.name or repo.full_name or "",
                full_name=repo.full_name or "",
                stargazers_count=repo.stargazers_count or 0,
                description=repo.description,
                html_url=repo.html_url,
                language=repo.language,
            )
            for repo in top_repositories
        ],
        top_languages=top_languages,
        sources=[_profile_source(username)],
        availability=availability,
    )
