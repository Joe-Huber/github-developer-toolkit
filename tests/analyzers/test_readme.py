"""Unit tests for README quality & structure analysis (issue #26).

Exercises the analyzer against a rich README, a minimal README, and a generic
template README, verifying per-signal metrics, heuristic boilerplate
detection, and findings that reference README sections and positions.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ghdtk.analyzers import assess_readme_quality
from ghdtk.models.derived import DimensionId, FindingSeverity, SourceEntityKind
from ghdtk.models.raw import ProfileReadme, ProfileReadmeStatus

NOW = datetime(2026, 1, 1, tzinfo=UTC)

RICH_README = """# Hi, I'm OctoCat

Welcome! I build tools for developers and maintain a few open source projects in my spare time.

## About

- Backend developer focused on Python and Go.
- Open source contributor.
- I enjoy automating boring workflows.

## Skills

- Python, Go, TypeScript
- PostgreSQL, Redis
- AWS, Docker, Kubernetes

## Contact

- [Email](mailto:octocat@users.noreply.github.com)
- [Twitter](https://twitter.com/octocat)

## Projects

Here is a small example of what I like to write:

~~~python
def hello(name: str) -> str:
    return f"Hello, {name}!"
~~~

That is it, simple and clean.

## Badges

![badge](https://img.shields.io/badge/python-3.12-blue)
![avatar](https://github.com/octocat.png)

Thanks for visiting, and feel free to reach out anytime.
"""

TEMPLATE_README = """# Your Name

Welcome to my GitHub profile. This is a readme template. Feel free to use this template.
"""


def _present(content: str, username: str = "octocat") -> ProfileReadme:
    return ProfileReadme(
        username=username,
        status=ProfileReadmeStatus.PRESENT,
        content=content,
        repository=f"{username}/{username}",
    )


def _absent(status: ProfileReadmeStatus) -> ProfileReadme:
    return ProfileReadme(username="octocat", status=status)


def _metric_ids(result: object) -> set[str]:
    return {metric.id for metric in result.metrics}  # type: ignore[attr-defined]


def _metric_value(result: object, metric_id: str) -> object:
    return next(metric for metric in result.metrics if metric.id == metric_id).value  # type: ignore[attr-defined]


def test_rich_readme_signals() -> None:
    result = assess_readme_quality(_present(RICH_README), now=NOW)

    assert result.status is ProfileReadmeStatus.PRESENT
    assert _metric_value(result, "readme.present") is True
    assert _metric_value(result, "readme.word_count") == 113
    assert _metric_value(result, "readme.headings") == 6
    assert _metric_value(result, "readme.code_blocks") == 1
    assert _metric_value(result, "readme.links") == 2
    assert _metric_value(result, "readme.images") == 2
    assert _metric_value(result, "readme.badges") == 1
    assert _metric_value(result, "readme.section.about") is True
    assert _metric_value(result, "readme.section.skills") is True
    assert _metric_value(result, "readme.section.contact") is True
    assert _metric_value(result, "readme.username_mentions") == 4


def test_rich_readme_has_no_negative_findings() -> None:
    result = assess_readme_quality(_present(RICH_README), now=NOW)

    finding_ids = {finding.id for finding in result.findings}
    assert {
        "readme.thin",
        "readme.no_heading",
        "readme.boilerplate",
        "readme.not_personalized",
        "readme.section.about.missing",
        "readme.section.skills.missing",
        "readme.section.contact.missing",
    }.isdisjoint(finding_ids)


def test_minimal_readme() -> None:
    result = assess_readme_quality(_present("hi"), now=NOW)

    assert _metric_value(result, "readme.word_count") == 1
    assert _metric_value(result, "readme.headings") == 0
    finding_ids = {finding.id for finding in result.findings}
    assert {
        "readme.thin",
        "readme.no_heading",
        "readme.not_personalized",
        "readme.section.about.missing",
        "readme.section.skills.missing",
        "readme.section.contact.missing",
    } <= finding_ids

    thin = next(finding for finding in result.findings if finding.id == "readme.thin")
    assert thin.severity is FindingSeverity.LOW


def test_template_readme_detects_boilerplate() -> None:
    result = assess_readme_quality(_present(TEMPLATE_README), now=NOW)

    boilerplate = next(finding for finding in result.findings if finding.id == "readme.boilerplate")
    assert boilerplate.severity is FindingSeverity.MEDIUM
    assert boilerplate.evidence[0].entity is SourceEntityKind.README
    assert boilerplate.evidence[0].field == "content:line:3"

    assert any(finding.id == "readme.not_personalized" for finding in result.findings)


def test_boilerplate_finding_messages_note_heuristic() -> None:
    result = assess_readme_quality(_present(TEMPLATE_README), now=NOW)

    boilerplate = next(finding for finding in result.findings if finding.id == "readme.boilerplate")
    assert "Heuristic match" in boilerplate.message
    assert "false positive" in boilerplate.message


def test_missing_readme_states() -> None:
    expected: dict[ProfileReadmeStatus, FindingSeverity] = {
        ProfileReadmeStatus.NO_PROFILE_REPO: FindingSeverity.LOW,
        ProfileReadmeStatus.NO_README: FindingSeverity.MEDIUM,
        ProfileReadmeStatus.EMPTY: FindingSeverity.MEDIUM,
    }
    for status, severity in expected.items():
        result = assess_readme_quality(_absent(status), now=NOW)
        assert result.status is status
        assert _metric_value(result, "readme.present") is False
        finding = next(
            finding for finding in result.findings if finding.id == f"readme.{status.value}"
        )
        assert finding.severity is severity
        assert finding.dimension == DimensionId.DOCUMENTATION


def test_fetch_failed_readme_state() -> None:
    profile_readme = ProfileReadme(
        username="octocat",
        status=ProfileReadmeStatus.FETCH_FAILED,
        reason="rate limit",
    )
    result = assess_readme_quality(profile_readme, now=NOW)

    finding = next(finding for finding in result.findings if finding.id == "readme.fetch_failed")
    assert finding.severity is FindingSeverity.LOW
    assert "rate limit" in finding.message


def test_readme_metrics_are_sources() -> None:
    result = assess_readme_quality(_present(RICH_README), now=NOW)

    headings_metric = next(metric for metric in result.metrics if metric.id == "readme.headings")
    assert headings_metric.sources[0].entity is SourceEntityKind.README
    assert headings_metric.sources[0].identifier == "octocat/octocat"

    about_metric = next(metric for metric in result.metrics if metric.id == "readme.section.about")
    assert about_metric.sources[0].field == "content:section:about"
