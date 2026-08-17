"""Metric availability matrix (issue #64).

Every metric family the analyzers emit is documented here: where GitHub's data
comes from, how reliable it is, the known caps and limits that bound it, and
the approximate request cost. Metrics GitHub does not reliably provide are
typed :class:`~ghdtk.models.derived.MetricAvailability.UNAVAILABLE` by the
analyzers; this matrix is the single source of truth that keeps those
guardrails documented and testable, so no report ever claims a value GitHub
does not expose.

The matrix is intentionally written for humans first (docs + code comments)
and exposed programmatically via :func:`availability_for` so tests can verify
the analyzers never emit a metric the matrix does not cover.
"""

from __future__ import annotations

from dataclasses import dataclass

from ghdtk.models.derived.metric import MetricAvailability

__all__ = ["MATRIX", "AvailabilityEntry", "availability_for"]


@dataclass(frozen=True)
class AvailabilityEntry:
    """Documented availability of one metric family."""

    family: str
    source: str
    reliability: str
    known_caps: str
    cost: str
    default: MetricAvailability = MetricAvailability.AVAILABLE


# The availability matrix. ``family`` is a metric-id prefix; ``default`` is the
# canonical typed availability for metrics in that family. Order matters only
# for prefix resolution (longest prefix wins).
MATRIX: tuple[AvailabilityEntry, ...] = (
    AvailabilityEntry(
        family="presence",
        source="User object (GET /users/{username})",
        reliability="High: GitHub reports account presence fields directly.",
        known_caps="Fields may be null for sparse/placeholder accounts.",
        cost="1 request.",
    ),
    AvailabilityEntry(
        family="readme",
        source="Repository README (GET /repos/{owner}/{repo}/readme)",
        reliability="High when a readme exists; absence is reported as missing.",
        known_caps="Pinned profile readme requires a separate profile collection.",
        cost="1 request per repository.",
    ),
    AvailabilityEntry(
        family="portfolio.quality",
        source="Repository metadata (GET /users/{username}/repos)",
        reliability="High: description/license/topics/homepage are direct fields.",
        known_caps="Forked and archived repositories are reported as such.",
        cost="Covered by the repository list collection.",
    ),
    AvailabilityEntry(
        family="portfolio.activity",
        source="Repository metadata (GET /users/{username}/repos)",
        reliability="Medium: reflects only the collected window, not lifetime.",
        known_caps="Bounded by the shared page cap and request budget.",
        cost="Covered by the repository list collection.",
        default=MetricAvailability.PARTIAL,
    ),
    AvailabilityEntry(
        family="portfolio",
        source="Repository list (GET /users/{username}/repos)",
        reliability="High: repo count, stars, forks, archived state are direct fields.",
        known_caps="Pagination bounded by the page cap and request budget.",
        cost="Covered by the repository list collection.",
    ),
    AvailabilityEntry(
        family="portfolio.stars",
        source="Repository list + stargazer timeline (preview header)",
        reliability="High: current stars are exact; timeline adds starred_at.",
        known_caps="Timeline pagination bounded by page cap.",
        cost="Up to page_cap requests for the top repository.",
    ),
    AvailabilityEntry(
        family="star_growth",
        source="Stargazer timeline (GET /repos/{owner}/{repo}/stargazers)",
        reliability="Medium: growth is computed over the collected timeline window.",
        known_caps="Only the most-starred owned repository is collected.",
        cost="Up to page_cap requests.",
        default=MetricAvailability.PARTIAL,
    ),
    AvailabilityEntry(
        family="network.followers.growth",
        source="None: GitHub exposes only the current follower count.",
        reliability="Unavailable by design; growth history is not exposed.",
        known_caps="No historical endpoint exists (the matrix documents this).",
        cost="0 requests.",
        default=MetricAvailability.UNAVAILABLE,
    ),
    AvailabilityEntry(
        family="network.orgs.count",
        source="None: the public user object exposes no org count field.",
        reliability="Unavailable by design; org membership requires extra scopes.",
        known_caps="No public field to count; would need the orgs endpoint.",
        cost="0 requests.",
        default=MetricAvailability.UNAVAILABLE,
    ),
    AvailabilityEntry(
        family="network.mutual_follows",
        source="Computed from follower + following lists.",
        reliability="Medium: only accurate when both lists were collected.",
        known_caps="Bounded by page cap on both list endpoints.",
        cost="Up to page_cap requests per list.",
        default=MetricAvailability.PARTIAL,
    ),
    AvailabilityEntry(
        family="network",
        source="User object + follower/following lists.",
        reliability="High for current counts; point-in-time snapshot only.",
        known_caps="Counts reflect collection time, not history.",
        cost="1 + up to page_cap requests per list.",
    ),
    AvailabilityEntry(
        family="commit_activity",
        source="Per-repository commits (GET /repos/{owner}/{repo}/commits?author=)",
        reliability="Medium: a window, not full lifetime history.",
        known_caps="Commit *search* (~1000/query) is not used; listing is bounded "
        "by page cap and request budget.",
        cost="Up to page_cap requests per repository.",
        default=MetricAvailability.PARTIAL,
    ),
    AvailabilityEntry(
        family="contribution_calendar",
        source="GraphQL contributionsCollection (GET /graphql)",
        reliability="Medium: the contribution calendar is a rolling ~365-day window.",
        known_caps="Private contributions may be hidden by the account.",
        cost="1 request.",
        default=MetricAvailability.PARTIAL,
    ),
    AvailabilityEntry(
        family="pull_requests",
        source="Search API + per-repository pulls (GET /search/issues, /pulls)",
        reliability="Medium: reflects the collected window, not lifetime.",
        known_caps="Search results and pagination bounded by page cap and budget.",
        cost="1 search + up to page_cap per repository.",
        default=MetricAvailability.PARTIAL,
    ),
    AvailabilityEntry(
        family="issues",
        source="Search API + per-repository issues (GET /search/issues, /issues)",
        reliability="Medium: reflects the collected window, not lifetime.",
        known_caps="Search results and pagination bounded by page cap and budget.",
        cost="1 search + up to page_cap per repository.",
        default=MetricAvailability.PARTIAL,
    ),
    AvailabilityEntry(
        family="languages",
        source="Per-repository languages (GET /repos/{owner}/{repo}/languages)",
        reliability="High: GitHub reports the language byte totals directly.",
        known_caps="Empty repositories report no language data.",
        cost="1 request per repository.",
    ),
    AvailabilityEntry(
        family="tech",
        source="Derived from per-repository language bytes.",
        reliability="High: domain mapping is deterministic over language bytes.",
        known_caps="Depends on language collection; unmapped bytes are disclosed.",
        cost="Covered by the language collections.",
    ),
)


def availability_for(metric_id: str) -> MetricAvailability:
    """Return the documented availability for a metric id (longest prefix)."""
    best: MetricAvailability | None = None
    best_length = -1
    for entry in MATRIX:
        if metric_id.startswith(entry.family) and len(entry.family) > best_length:
            best = entry.default
            best_length = len(entry.family)
    return MetricAvailability.AVAILABLE if best is None else best
