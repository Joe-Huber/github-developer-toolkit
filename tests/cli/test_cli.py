"""Unit tests for the CLI entry point."""

from __future__ import annotations

import os

import pytest

from ghdtk.cli import main


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("GHDTK_"):
            monkeypatch.delenv(key, raising=False)


def test_version_prints_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "ghdtk" in capsys.readouterr().out


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage:" in capsys.readouterr().out


def test_config_without_token_fails(capsys: pytest.CaptureFixture[str]) -> None:
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
