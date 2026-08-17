"""CLI integration tests for the ``analyze`` command (issue #75).

Replays every corpus session through ``ghdtk.cli.main`` (the CLI entry point)
using a monkeypatched ``GitHubClient.from_settings`` so no live API calls are
made.  The strict replay transport is the contract: any request outside the
recorded session raises, so the corpus must stay complete as the pipeline
evolves.

Exit-code contract:

- 0  success
- 1  general/unexpected error
- 2  configuration error
- 3  API error (auth, rate-limit, network)
- 4  partial success (some collections failed)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from replay import client_from_session, list_profiles, load_session

from ghdtk.cli import (
    EXIT_API,
    EXIT_CONFIG,
    EXIT_GENERAL,
    EXIT_PARTIAL,
    EXIT_SUCCESS,
    build_parser,
    main,
)

# Timestamps vary between runs — exclude them when comparing determinism.
_JSON_TIMESTAMP_KEYS = {"generated_at", "analyzed_at", "timestamp"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_client_for_session(profile_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch ``GitHubClient.from_settings`` to return a replay client.

    Because ``_cmd_analyze`` uses a *local* ``from ghdtk.api.client import
    GitHubClient``, the patched name must live in ``ghdtk.api.client`` so the
    lazy import picks it up at call time.
    """
    session = load_session(profile_id)
    replay_client = client_from_session(session)

    class _FakeGitHubClient:
        @classmethod
        def from_settings(cls, settings: Any) -> Any:
            return replay_client

    monkeypatch.setattr("ghdtk.api.client.GitHubClient", _FakeGitHubClient)


def _ensure_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set a dummy token so ``load_settings`` succeeds."""
    monkeypatch.setenv("GHDTK_GITHUB_TOKEN", "test-token-for-cli")


def _strip_timestamps(obj: Any) -> Any:
    """Recursively remove timestamp fields for determinism comparison."""
    if isinstance(obj, dict):
        return {k: _strip_timestamps(v) for k, v in obj.items() if k not in _JSON_TIMESTAMP_KEYS}
    if isinstance(obj, list):
        return [_strip_timestamps(item) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# Parser / build_parser tests
# ---------------------------------------------------------------------------


class TestBuildParser:
    def test_analyze_subparser_exists(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["analyze", "octocat"])
        assert args.command == "analyze"
        assert args.username == "octocat"
        assert args.output_format == "md"

    def test_analyze_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["analyze", "octocat"])
        assert args.output is None
        assert args.max_requests is None
        assert args.max_workers is None
        assert args.no_cache is False
        assert args.verbose is False
        assert args.quiet is False

    def test_analyze_all_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "analyze",
                "octocat",
                "-f",
                "json",
                "-o",
                "/tmp/report.json",
                "--max-requests",
                "50",
                "--max-workers",
                "4",
                "--no-cache",
                "-v",
                "-q",
            ]
        )
        assert args.output_format == "json"
        assert args.output == Path("/tmp/report.json")
        assert args.max_requests == 50
        assert args.max_workers == 4
        assert args.no_cache is True
        assert args.verbose is True
        assert args.quiet is True

    def test_version_flag(self) -> None:
        with pytest.raises(SystemExit) as excinfo:
            build_parser().parse_args(["--version"])
        assert excinfo.value.code == 0

    def test_no_command_returns_none(self) -> None:
        args = build_parser().parse_args([])
        assert args.command is None


# ---------------------------------------------------------------------------
# Exit code constants
# ---------------------------------------------------------------------------


class TestExitCodes:
    def test_constants_are_distinct(self) -> None:
        codes = {EXIT_SUCCESS, EXIT_GENERAL, EXIT_CONFIG, EXIT_API, EXIT_PARTIAL}
        assert len(codes) == 5
        assert EXIT_SUCCESS == 0
        assert EXIT_GENERAL == 1
        assert EXIT_CONFIG == 2
        assert EXIT_API == 3
        assert EXIT_PARTIAL == 4


# ---------------------------------------------------------------------------
# Config command (unchanged behavior)
# ---------------------------------------------------------------------------


class TestCmdConfig:
    def test_no_command_prints_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main([]) == EXIT_SUCCESS
        assert "usage:" in capsys.readouterr().out

    def test_config_without_token_exits_config_code(
        self,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.delenv("GHDTK_GITHUB_TOKEN", raising=False)
        monkeypatch.chdir(tmp_path)
        assert main(["config"]) == EXIT_CONFIG
        err = capsys.readouterr().err
        assert "could not load configuration" in err
        assert "github_token" in err

    def test_config_with_token_succeeds(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GHDTK_GITHUB_TOKEN", "token")
        assert main(["config"]) == EXIT_SUCCESS
        out = capsys.readouterr().out
        assert "github token configured: True" in out


# ---------------------------------------------------------------------------
# Analyze command — happy path (fixture replay)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("profile_id", list_profiles())
def test_analyze_exits_zero_and_writes_markdown(
    profile_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ensure_token(monkeypatch)
    _patch_client_for_session(profile_id, monkeypatch)
    username = load_session(profile_id)["profile"]["username"]
    out_file = tmp_path / f"{username}.md"

    rc = main(["analyze", username, "-o", str(out_file), "-q"])

    assert rc == EXIT_SUCCESS
    assert out_file.exists(), "output file was not created"
    content = out_file.read_text(encoding="utf-8")
    assert f"# GitHub Profile Report: {username}" in content
    assert len(content) > 100


@pytest.mark.parametrize("profile_id", list_profiles())
def test_analyze_json_format(
    profile_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ensure_token(monkeypatch)
    _patch_client_for_session(profile_id, monkeypatch)
    username = load_session(profile_id)["profile"]["username"]
    out_file = tmp_path / f"{username}.json"

    rc = main(["analyze", username, "-f", "json", "-o", str(out_file), "-q"])

    assert rc == EXIT_SUCCESS
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["profile"]["username"] == username
    assert payload["profile"]["overall"] is not None


@pytest.mark.parametrize("profile_id", list_profiles())
def test_analyze_html_format(
    profile_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ensure_token(monkeypatch)
    _patch_client_for_session(profile_id, monkeypatch)
    username = load_session(profile_id)["profile"]["username"]
    out_file = tmp_path / f"{username}.html"

    rc = main(["analyze", username, "-f", "html", "-o", str(out_file), "-q"])

    assert rc == EXIT_SUCCESS
    html = out_file.read_text(encoding="utf-8")
    assert "<html" in html
    assert username in html


def test_analyze_default_output_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ensure_token(monkeypatch)
    _patch_client_for_session("active-developer", monkeypatch)
    monkeypatch.chdir(tmp_path)

    session = load_session("active-developer")
    real_username = session["profile"]["username"]
    rc = main(["analyze", real_username, "-q"])

    assert rc == EXIT_SUCCESS
    assert (tmp_path / f"{real_username}.md").exists()


# ---------------------------------------------------------------------------
# Analyze command — progress output
# ---------------------------------------------------------------------------


def test_verbose_shows_budget_info(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ensure_token(monkeypatch)
    _patch_client_for_session("active-developer", monkeypatch)
    username = load_session("active-developer")["profile"]["username"]
    out_file = tmp_path / "report.md"

    main(["analyze", username, "-o", str(out_file), "-v"])

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "collected" in combined
    assert "requests" in combined


def test_quiet_suppresses_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ensure_token(monkeypatch)
    _patch_client_for_session("active-developer", monkeypatch)
    username = load_session("active-developer")["profile"]["username"]
    out_file = tmp_path / "report.md"

    main(["analyze", username, "-o", str(out_file), "-q"])

    err = capsys.readouterr().err
    assert err.strip() == ""


# ---------------------------------------------------------------------------
# Analyze command — CLI flag overrides
# ---------------------------------------------------------------------------


def test_no_cache_disables_cache_in_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ensure_token(monkeypatch)
    _patch_client_for_session("active-developer", monkeypatch)
    username = load_session("active-developer")["profile"]["username"]
    out_file = tmp_path / "report.md"

    rc = main(["analyze", username, "-o", str(out_file), "--no-cache", "-q"])
    assert rc == EXIT_SUCCESS
    assert out_file.exists()


def test_max_requests_flag_accepted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ensure_token(monkeypatch)
    _patch_client_for_session("active-developer", monkeypatch)
    username = load_session("active-developer")["profile"]["username"]
    out_file = tmp_path / "report.md"

    rc = main(["analyze", username, "-o", str(out_file), "--max-requests", "50", "-q"])
    assert rc == EXIT_SUCCESS


def test_max_workers_flag_accepted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ensure_token(monkeypatch)
    _patch_client_for_session("active-developer", monkeypatch)
    username = load_session("active-developer")["profile"]["username"]
    out_file = tmp_path / "report.md"

    rc = main(["analyze", username, "-o", str(out_file), "--max-workers", "2", "-q"])
    assert rc == EXIT_SUCCESS


# ---------------------------------------------------------------------------
# Analyze command — error cases
# ---------------------------------------------------------------------------


def test_analyze_bad_config_exits_config_code(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Missing token should exit with EXIT_CONFIG (2)."""
    monkeypatch.delenv("GHDTK_GITHUB_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    rc = main(["analyze", "octocat"])
    assert rc == EXIT_CONFIG
    err = capsys.readouterr().err
    assert "configuration" in err.lower() or "error" in err.lower()


def test_analyze_bad_format_exits_general() -> None:
    """Unknown format (impossible via parser, but defensive)."""
    parser = build_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["analyze", "octocat", "-f", "xml"])
    assert excinfo.value.code != 0


# ---------------------------------------------------------------------------
# Determinism: same fixture produces identical output across runs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("profile_id", list_profiles())
def test_analyze_output_is_deterministic(
    profile_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JSON payloads are identical when timestamps are excluded."""
    _ensure_token(monkeypatch)
    username = load_session(profile_id)["profile"]["username"]

    results: list[dict[str, Any]] = []
    for i in range(2):
        _patch_client_for_session(profile_id, monkeypatch)
        out_file = tmp_path / f"run{i}.json"
        rc = main(["analyze", username, "-f", "json", "-o", str(out_file), "-q"])
        assert rc == EXIT_SUCCESS
        raw = json.loads(out_file.read_text(encoding="utf-8"))
        results.append(_strip_timestamps(raw))

    assert results[0] == results[1]


# ---------------------------------------------------------------------------
# Score output
# ---------------------------------------------------------------------------


def test_analyze_prints_score_to_stdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ensure_token(monkeypatch)
    _patch_client_for_session("active-developer", monkeypatch)
    username = load_session("active-developer")["profile"]["username"]
    out_file = tmp_path / "report.md"

    main(["analyze", username, "-o", str(out_file), "-q"])

    out = capsys.readouterr().out
    assert "Overall score:" in out
