"""Unit tests for the CLI entry point."""

from __future__ import annotations

import os
import webbrowser
from pathlib import Path
from unittest.mock import Mock

import pytest

from ghdtk.cli import main

uvicorn = pytest.importorskip("uvicorn")


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("GHDTK_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def _stop_server(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uvicorn, "run", Mock())


@pytest.fixture
def _capture_browser(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    opened: list[str] = []
    monkeypatch.setattr(webbrowser, "open", opened.append)
    return opened


def test_version_prints_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "ghdtk" in capsys.readouterr().out


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage:" in capsys.readouterr().out


def test_config_without_token_fails(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("GHDTK_GITHUB_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    assert main(["config"]) == 2
    err = capsys.readouterr().err
    assert "could not load configuration" in err
    assert "github_token" in err


def test_config_with_token_succeeds(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GHDTK_GITHUB_TOKEN", "token")
    assert main(["config"]) == 0
    out = capsys.readouterr().out
    assert "github token configured: True" in out
    assert "cache: enabled" in out


def test_dashboard_opens_browser_with_username_query(
    capsys: pytest.CaptureFixture[str], _stop_server: None, _capture_browser: list[str]
) -> None:
    assert main(["dashboard", "octocat", "--port", "8123"]) == 0
    assert _capture_browser == ["http://127.0.0.1:8123/?user=octocat"]
    err = capsys.readouterr().err
    assert "Dashboard serving @octocat at http://127.0.0.1:8123" in err


def test_dashboard_without_username_opens_plain_url(
    capsys: pytest.CaptureFixture[str], _stop_server: None, _capture_browser: list[str]
) -> None:
    assert main(["dashboard", "--no-open", "--port", "8123"]) == 0
    assert _capture_browser == []
    err = capsys.readouterr().err
    assert "Dashboard serving at http://127.0.0.1:8123" in err
