"""Evidence-backed recommendation rule library (issue #52).

The library maps every finding emitted by the analysis epics to one of three
outcomes:

- **Actionable** — a :class:`RecommendationRule` produces a recommendation with
  a template id, action and rationale.
- **Disclosure** (:data:`DISCLOSURE_PREFIXES`) — informational findings about
  missing or possibly misleading data. They surface as red flags in the
  synthesis but carry no actionable recommendation.
- **Positive** (:data:`POSITIVE_PREFIXES`) — standout findings that surface as
  strengths in the synthesis but need no action.

Rules match findings by id: exact ids (``presence.bio.short``), dotted-prefix
ids (``repo.activity.stale.`` matches every ``repo.activity.stale.<repo>``) and
patterns with a single ``*`` wildcard segment (``presence.*.missing`` matches
``presence.name.missing``). A rule can declare a ``var`` whose value is
extracted from the matched id and used as a template placeholder.
"""

from __future__ import annotations

from dataclasses import dataclass

from ghdtk.models.derived import RecommendationEffort, RecommendationPriority


@dataclass(frozen=True)
class RecommendationRule:
    """One templated recommendation rule for a finding pattern."""

    id: str
    applies_to: str
    action: str
    rationale: str
    effort: RecommendationEffort
    priority: RecommendationPriority
    var: str | None = None
    metrics: tuple[str, ...] = ()


def match_rule(
    finding_id: str, rules: tuple[RecommendationRule, ...] = ()
) -> RecommendationRule | None:
    """Return the rule for a finding id, or ``None``.

    With no ``rules`` argument the :data:`DEFAULT_RULES` library is used. A
    finding matches an actionable rule only; disclosures and positives match
    nothing here.
    """
    rules = rules or DEFAULT_RULES
    for rule in rules:
        if _matches(rule.applies_to, finding_id):
            return rule
    return None


def extract_value(rule: RecommendationRule, finding_id: str) -> str | None:
    """Extract the rule's variable value from a matching finding id."""
    if rule.var is None:
        return None
    pattern = rule.applies_to
    if "*" in pattern:
        prefix, suffix = pattern.split("*", 1)
        return finding_id[len(prefix) : len(finding_id) - len(suffix)]
    if pattern.endswith("."):
        return finding_id[len(pattern) :]
    return None


def _matches(pattern: str, finding_id: str) -> bool:
    if "*" in pattern:
        prefix, suffix = pattern.split("*", 1)
        if not finding_id.startswith(prefix) or not finding_id.endswith(suffix):
            return False
        middle = finding_id[len(prefix) : len(finding_id) - len(suffix)]
        return "." not in middle and bool(middle)
    return finding_id == pattern or finding_id.startswith(pattern)


def classify(finding_id: str) -> str:
    """Classify a finding id as ``actionable``, ``disclosure`` or ``positive``.

    Raises ``ValueError`` for ids the library does not recognize, so a missing
    rule is caught immediately rather than silently ignored.
    """
    if match_rule(finding_id) is not None:
        return "actionable"
    if any(finding_id == prefix or finding_id.startswith(prefix) for prefix in DISCLOSURE_PREFIXES):
        return "disclosure"
    if any(finding_id == prefix or finding_id.startswith(prefix) for prefix in POSITIVE_PREFIXES):
        return "positive"
    raise ValueError(f"no rule, disclosure or positive classifies finding id {finding_id!r}")


DEFAULT_RULES: tuple[RecommendationRule, ...] = (
    # --- Profile presence ---------------------------------------------------
    RecommendationRule(
        id="presence.field.missing",
        applies_to="presence.*.missing",
        var="field",
        action="Add your {field} to your GitHub profile.",
        rationale="The profile is missing its {field}.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.MEDIUM,
        metrics=("presence.fields.missing",),
    ),
    RecommendationRule(
        id="presence.field.placeholder",
        applies_to="presence.*.placeholder",
        var="field",
        action="Replace the placeholder {field} on your GitHub profile with real information.",
        rationale="The profile's {field} looks like placeholder text rather than real information.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.HIGH,
        metrics=("presence.fields.placeholder",),
    ),
    RecommendationRule(
        id="presence.expand_bio",
        applies_to="presence.bio.short",
        action="Expand your bio to describe what you work on and what you are interested in.",
        rationale="The bio is too short to convey the profile's focus.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.MEDIUM,
        metrics=("presence.bio",),
    ),
    RecommendationRule(
        id="presence.set_hireable",
        applies_to="presence.hireable.unset",
        action='Set your availability ("available for hire") status on your GitHub profile.',
        rationale="The profile does not state whether the account owner is available for hire.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.MEDIUM,
    ),
    RecommendationRule(
        id="presence.build_history",
        applies_to="presence.account.recent",
        action=(
            "Keep building out your profile; a very recent account has little "
            "history to assess yet."
        ),
        rationale="The account is very recent, so there is little history to assess.",
        effort=RecommendationEffort.MEDIUM,
        priority=RecommendationPriority.LOW,
        metrics=("presence.account_age_days",),
    ),
    # --- Profile README -----------------------------------------------------
    RecommendationRule(
        id="readme.create_profile_repo",
        applies_to="readme.no_profile_repo",
        action="Create a {username}/{username} repository with a README.md.",
        rationale="There is no profile repository for {username}.",
        effort=RecommendationEffort.MEDIUM,
        priority=RecommendationPriority.HIGH,
    ),
    RecommendationRule(
        id="readme.create_readme",
        applies_to="readme.no_readme",
        action="Add a README.md to your {username}/{username} profile repository.",
        rationale="The profile repository has no README.",
        effort=RecommendationEffort.MEDIUM,
        priority=RecommendationPriority.HIGH,
    ),
    RecommendationRule(
        id="readme.write_content",
        applies_to="readme.empty",
        action="Write an introduction in your profile README.",
        rationale="The profile README is empty.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.HIGH,
    ),
    RecommendationRule(
        id="readme.verify_accessible",
        applies_to="readme.fetch_failed",
        action="Check that your profile repository and README are public and reachable.",
        rationale="The profile README could not be fetched.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.MEDIUM,
    ),
    RecommendationRule(
        id="readme.expand_readme",
        applies_to="readme.thin",
        action="Expand your profile README with more detail about who you are.",
        rationale="The profile README is very short.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.MEDIUM,
    ),
    RecommendationRule(
        id="readme.add_headings",
        applies_to="readme.no_heading",
        action="Structure your profile README with clear headings.",
        rationale="The profile README has no descriptive headings.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.MEDIUM,
    ),
    RecommendationRule(
        id="readme.add_section",
        applies_to="readme.section.*.missing",
        var="section",
        action="Add an '{section}' section to your profile README.",
        rationale="The profile README is missing its {section} section.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.MEDIUM,
    ),
    RecommendationRule(
        id="readme.personalize",
        applies_to="readme.not_personalized",
        action="Personalize your profile README so it reflects your own work.",
        rationale="The profile README does not mention {username} anywhere.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.MEDIUM,
    ),
    RecommendationRule(
        id="readme.replace_boilerplate",
        applies_to="readme.boilerplate",
        action="Rewrite the template language in your profile README in your own words.",
        rationale="The profile README contains boilerplate language.",
        effort=RecommendationEffort.MEDIUM,
        priority=RecommendationPriority.HIGH,
    ),
    # --- Repository quality -------------------------------------------------
    RecommendationRule(
        id="repo.add_description",
        applies_to="repo.quality.no_description.",
        var="full_name",
        action="Add a description to the {full_name} repository.",
        rationale="The {full_name} repository has no description.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.HIGH,
    ),
    RecommendationRule(
        id="repo.fix_placeholder_description",
        applies_to="repo.quality.placeholder_description.",
        var="full_name",
        action="Replace the placeholder description of {full_name} with a real one.",
        rationale="The {full_name} description is placeholder text.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.HIGH,
    ),
    RecommendationRule(
        id="repo.add_readme",
        applies_to="repo.quality.no_readme.",
        var="full_name",
        action="Add a README to {full_name} so others can understand the project.",
        rationale="The {full_name} repository has no README.",
        effort=RecommendationEffort.MEDIUM,
        priority=RecommendationPriority.HIGH,
    ),
    RecommendationRule(
        id="repo.expand_repo_readme",
        applies_to="repo.quality.thin_readme.",
        var="full_name",
        action="Expand the README of {full_name}; it is currently very short.",
        rationale="The {full_name} README is very short.",
        effort=RecommendationEffort.MEDIUM,
        priority=RecommendationPriority.MEDIUM,
    ),
    RecommendationRule(
        id="portfolio.describe_repositories",
        applies_to="portfolio.quality.low_description_coverage",
        action="Add a description to each of your repositories.",
        rationale="Most of your repositories lack descriptions.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.HIGH,
        metrics=("portfolio.quality.description_coverage",),
    ),
    RecommendationRule(
        id="portfolio.add_repo_readmes",
        applies_to="portfolio.quality.low_readme_coverage",
        action="Add a README to each of your repositories.",
        rationale="Most of your repositories lack READMEs.",
        effort=RecommendationEffort.MEDIUM,
        priority=RecommendationPriority.HIGH,
        metrics=("portfolio.quality.readme_coverage",),
    ),
    # --- Repository activity ------------------------------------------------
    RecommendationRule(
        id="repo.stale_repository",
        applies_to="repo.activity.stale.",
        var="full_name",
        action="Push a commit to {full_name} or archive it if the project is finished.",
        rationale="The {full_name} repository has been inactive for a while.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.MEDIUM,
    ),
    RecommendationRule(
        id="portfolio.show_recent_activity",
        applies_to="portfolio.activity.no_recent_activity",
        action="Push recent work to a repository so your profile shows active development.",
        rationale="None of your repositories had activity in the assessment window.",
        effort=RecommendationEffort.MEDIUM,
        priority=RecommendationPriority.HIGH,
    ),
    RecommendationRule(
        id="portfolio.revive_long_inactive",
        applies_to="portfolio.activity.longest_inactive_months",
        action="Update or archive a repository that has been inactive for over a year.",
        rationale="One of your repositories has been inactive for a long time.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.LOW,
    ),
    # --- Portfolio composition ----------------------------------------------
    RecommendationRule(
        id="portfolio.diversify_stars",
        applies_to="portfolio.composition.star_concentration",
        action=(
            "Grow your other repositories so your popularity is not concentrated in one project."
        ),
        rationale="Most of your stars come from a single repository.",
        effort=RecommendationEffort.MEDIUM,
        priority=RecommendationPriority.MEDIUM,
    ),
    RecommendationRule(
        id="portfolio.build_owned_projects",
        applies_to="portfolio.composition.fork_dominated",
        action="Create original projects you own instead of mostly forked repositories.",
        rationale="Most of your repositories are forks.",
        effort=RecommendationEffort.MEDIUM,
        priority=RecommendationPriority.HIGH,
    ),
    # --- Stars --------------------------------------------------------------
    RecommendationRule(
        id="portfolio.build_original_starred",
        applies_to="portfolio.stars.fork_star_share",
        action=(
            "Build original projects that earn their own stars rather than relying on fork stars."
        ),
        rationale="A large share of your stars come from forked repositories.",
        effort=RecommendationEffort.MEDIUM,
        priority=RecommendationPriority.MEDIUM,
    ),
    # --- Star growth --------------------------------------------------------
    RecommendationRule(
        id="star_growth.reinvigorate_momentum",
        applies_to="star_growth.slowing",
        action=(
            "Share updates on the project, publish releases, or refresh the "
            "README to rebuild momentum."
        ),
        rationale="Star growth has slowed recently.",
        effort=RecommendationEffort.MEDIUM,
        priority=RecommendationPriority.MEDIUM,
    ),
    # --- Follower network ---------------------------------------------------
    RecommendationRule(
        id="network.grow_audience",
        applies_to="network.followers.network_driven",
        action="Share your work consistently to grow an audience that follows you back.",
        rationale="You follow many more accounts than follow you.",
        effort=RecommendationEffort.MEDIUM,
        priority=RecommendationPriority.MEDIUM,
    ),
    # --- Commit activity ----------------------------------------------------
    RecommendationRule(
        id="commit_activity.start_committing",
        applies_to="commit_activity.no_commits",
        action="Push your projects to GitHub to build a visible commit history.",
        rationale="The profile shows no commit history.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.MEDIUM,
    ),
    RecommendationRule(
        id="commit_activity.commit_regularly",
        applies_to="commit_activity.long_gap",
        action="Commit more regularly to avoid long gaps in your history.",
        rationale="There is a long gap between commits.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.MEDIUM,
        metrics=("commit_activity.longest_gap_days",),
    ),
    # --- Contribution calendar ---------------------------------------------
    RecommendationRule(
        id="contribution_calendar.keep_cadence",
        applies_to="contribution_calendar.long_gap",
        action="Keep a steady contribution cadence so your calendar shows consistent activity.",
        rationale="There is a long gap in your contribution history.",
        effort=RecommendationEffort.LOW,
        priority=RecommendationPriority.MEDIUM,
        metrics=("contribution_calendar.longest_gap_days",),
    ),
    # --- Issue participation ------------------------------------------------
    RecommendationRule(
        id="issues.participate_actively",
        applies_to="issues.trend_slowing",
        action="Stay engaged with issues in projects you use to keep participation up.",
        rationale="Issue participation has slowed recently.",
        effort=RecommendationEffort.MEDIUM,
        priority=RecommendationPriority.MEDIUM,
    ),
    # --- Language distribution ----------------------------------------------
    RecommendationRule(
        id="languages.broaden_stack",
        applies_to="languages.concentrated",
        action="Explore other languages to broaden your technical stack.",
        rationale="Most of your code concentrates in a single language.",
        effort=RecommendationEffort.MEDIUM,
        priority=RecommendationPriority.LOW,
    ),
)


DISCLOSURE_PREFIXES: frozenset[str] = frozenset(
    {
        "repo.activity.archived.",
        "portfolio.composition.small_portfolio",
        "portfolio.standout.none_identified",
        "portfolio.stars.no_stars",
        "star_growth.no_timeline",
        "star_growth.insufficient_data",
        "network.followers.zero",
        "network.followers.partial_sample",
        "network.mutual_follows.unavailable",
        "network.followers.growth_unavailable",
        "network.orgs.unavailable",
        "commit_activity.coverage_window",
        "commit_activity.no_dates",
        "contribution_calendar.unavailable",
        "contribution_calendar.no_activity",
        "contribution_calendar.private_contributions",
        "pull_requests.no_pull_requests",
        "pull_requests.coverage_window",
        "issues.no_issues",
        "issues.coverage_window",
        "issues.trend_insufficient",
        "languages.no_repositories",
        "languages.no_data",
        "languages.coverage_gap",
        "languages.empty_repositories",
        "tech.no_evidence",
        "tech.no_byte_evidence",
        "tech.no_mapped_domains",
        "tech.low_mapping_coverage",
    }
)


POSITIVE_PREFIXES: frozenset[str] = frozenset(
    {
        "repo.standout.",
        "star_growth.rising",
        "network.followers.audience_driven",
        "commit_activity.consistent_cadence",
        "commit_activity.top_repo",
        "contribution_calendar.notable_streak",
        "pull_requests.external_engagement",
        "pull_requests.collaboration",
        "issues.external_engagement",
        "issues.community_participation",
        "issues.trend_rising",
        "languages.polyglot",
        "tech.specialized",
        "tech.diverse",
    }
)
