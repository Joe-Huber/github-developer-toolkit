"""Unit tests for the recommendation rule library (issue #52).

Covers rule matching (exact, dotted-prefix and wildcard patterns), variable
extraction, and the guarantee that every finding emitted by the analysis epics
is classified as actionable, a disclosure or a positive standout.
"""

from __future__ import annotations

import pytest

from ghdtk.recommendations.rules import (
    DEFAULT_RULES,
    DISCLOSURE_PREFIXES,
    POSITIVE_PREFIXES,
    classify,
    extract_value,
    match_rule,
)


def test_rule_matches_exact_id() -> None:
    rule = match_rule("presence.bio.short")
    assert rule is not None
    assert rule.id == "presence.expand_bio"


def test_rule_matches_dotted_prefix() -> None:
    rule = match_rule("repo.quality.no_description.octocat/hello")
    assert rule is not None
    assert rule.id == "repo.add_description"


def test_rule_matches_wildcard_segment() -> None:
    assert match_rule("presence.name.missing") is not None
    assert match_rule("presence.email.missing") is not None
    assert match_rule("readme.section.contact.missing") is not None


def test_wildcard_does_not_match_multi_segment() -> None:
    assert match_rule("presence.extra.segment.missing") is None


def test_no_rule_for_unknown_id() -> None:
    assert match_rule("unknown.finding") is None


def test_extract_field_from_wildcard() -> None:
    rule = match_rule("presence.company.missing")
    assert rule is not None
    assert extract_value(rule, "presence.company.missing") == "company"


def test_extract_section_from_wildcard() -> None:
    rule = match_rule("readme.section.skills.missing")
    assert rule is not None
    assert extract_value(rule, "readme.section.skills.missing") == "skills"


def test_extract_full_name_from_prefix() -> None:
    rule = match_rule("repo.activity.stale.octocat/hello")
    assert rule is not None
    assert extract_value(rule, "repo.activity.stale.octocat/hello") == "octocat/hello"


@pytest.mark.parametrize(
    ("finding_id", "expected"),
    [
        ("presence.name.missing", "actionable"),
        ("presence.bio.short", "actionable"),
        ("presence.blog.placeholder", "actionable"),
        ("presence.hireable.unset", "actionable"),
        ("presence.account.recent", "actionable"),
        ("readme.no_profile_repo", "actionable"),
        ("readme.no_readme", "actionable"),
        ("readme.empty", "actionable"),
        ("readme.fetch_failed", "actionable"),
        ("readme.thin", "actionable"),
        ("readme.no_heading", "actionable"),
        ("readme.section.about.missing", "actionable"),
        ("readme.not_personalized", "actionable"),
        ("readme.boilerplate", "actionable"),
        ("repo.quality.no_description.octocat/hello", "actionable"),
        ("repo.quality.placeholder_description.octocat/hello", "actionable"),
        ("repo.quality.no_readme.octocat/hello", "actionable"),
        ("repo.quality.thin_readme.octocat/hello", "actionable"),
        ("portfolio.quality.low_description_coverage", "actionable"),
        ("portfolio.quality.low_readme_coverage", "actionable"),
        ("repo.activity.stale.octocat/hello", "actionable"),
        ("portfolio.activity.no_recent_activity", "actionable"),
        ("portfolio.activity.longest_inactive_months", "actionable"),
        ("portfolio.composition.star_concentration", "actionable"),
        ("portfolio.composition.fork_dominated", "actionable"),
        ("portfolio.stars.fork_star_share", "actionable"),
        ("star_growth.slowing", "actionable"),
        ("network.followers.network_driven", "actionable"),
        ("commit_activity.no_commits", "actionable"),
        ("commit_activity.long_gap", "actionable"),
        ("contribution_calendar.long_gap", "actionable"),
        ("issues.trend_slowing", "actionable"),
        ("languages.concentrated", "actionable"),
        ("repo.activity.archived.octocat/hello", "disclosure"),
        ("portfolio.composition.small_portfolio", "disclosure"),
        ("portfolio.standout.none_identified", "disclosure"),
        ("portfolio.stars.no_stars", "disclosure"),
        ("star_growth.no_timeline", "disclosure"),
        ("star_growth.insufficient_data", "disclosure"),
        ("network.followers.zero", "disclosure"),
        ("network.followers.partial_sample", "disclosure"),
        ("network.mutual_follows.unavailable", "disclosure"),
        ("network.followers.growth_unavailable", "disclosure"),
        ("network.orgs.unavailable", "disclosure"),
        ("commit_activity.coverage_window", "disclosure"),
        ("commit_activity.no_dates", "disclosure"),
        ("contribution_calendar.unavailable", "disclosure"),
        ("contribution_calendar.no_activity", "disclosure"),
        ("contribution_calendar.private_contributions", "disclosure"),
        ("pull_requests.no_pull_requests", "disclosure"),
        ("pull_requests.coverage_window", "disclosure"),
        ("issues.no_issues", "disclosure"),
        ("issues.coverage_window", "disclosure"),
        ("issues.trend_insufficient", "disclosure"),
        ("languages.no_repositories", "disclosure"),
        ("languages.no_data", "disclosure"),
        ("languages.coverage_gap", "disclosure"),
        ("languages.empty_repositories", "disclosure"),
        ("tech.no_evidence", "disclosure"),
        ("tech.no_byte_evidence", "disclosure"),
        ("tech.no_mapped_domains", "disclosure"),
        ("tech.low_mapping_coverage", "disclosure"),
        ("repo.standout.octocat/hello", "positive"),
        ("star_growth.rising", "positive"),
        ("network.followers.audience_driven", "positive"),
        ("commit_activity.consistent_cadence", "positive"),
        ("commit_activity.top_repo", "positive"),
        ("contribution_calendar.notable_streak", "positive"),
        ("pull_requests.external_engagement", "positive"),
        ("pull_requests.collaboration", "positive"),
        ("issues.external_engagement", "positive"),
        ("issues.community_participation", "positive"),
        ("issues.trend_rising", "positive"),
        ("languages.polyglot", "positive"),
        ("tech.specialized", "positive"),
        ("tech.diverse", "positive"),
    ],
)
def test_classify_covers_all_known_findings(finding_id: str, expected: str) -> None:
    assert classify(finding_id) == expected


def test_classify_rejects_unrecognized_finding() -> None:
    with pytest.raises(ValueError):
        classify("never.emitted.finding")


def test_rule_defaults_are_sane() -> None:
    for rule in DEFAULT_RULES:
        assert rule.id
        assert rule.applies_to
        assert rule.action
        assert rule.rationale
        assert not rule.id.startswith("low_score")


def test_disclosure_and_positive_sets_are_consistent() -> None:
    overlap = DISCLOSURE_PREFIXES & POSITIVE_PREFIXES
    assert not overlap
