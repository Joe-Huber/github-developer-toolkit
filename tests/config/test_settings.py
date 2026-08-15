"""Unit tests for configuration parsing.

Covers config file + environment variable loading, documented precedence,
defaults, and clear errors on bad input (see issue #13).
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from ghdtk.config import Settings, load_settings, resolve_config_path

_TOKEN = "GHDTK_GITHUB_TOKEN"
_CONFIG_VAR = "GHDTK_CONFIG_FILE"


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove any GHDTK_* variables so tests run from a clean slate."""
    for key in list(os.environ):
        if key.startswith("GHDTK_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate CWD (for .env / ghdtk.toml discovery) in a temp dir."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


# --- defaults & required fields -------------------------------------------


def test_token_required(project_dir: Path) -> None:
    with pytest.raises(ValidationError):
        load_settings()


def test_defaults(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_TOKEN, "token")
    settings = load_settings()
    assert settings.github_base_url == "https://api.github.com"
    assert settings.github_timeout_seconds == 30.0
    assert settings.github_max_retries == 3
    assert settings.github_per_page == 100
    assert settings.cache_enabled is True
    assert settings.cache_ttl_seconds == 86_400
    assert settings.cache_dir is None
    assert settings.collection_max_requests == 500
    assert settings.analysis_minimum_stars == 10
    assert settings.analysis_minimum_commits == 5
    assert settings.analysis_minimum_repositories == 3
    assert settings.analysis_readme_min_chars == 100
    assert settings.analysis_staleness_days == 90


# --- config file -----------------------------------------------------------


def test_toml_file_values(project_dir: Path) -> None:
    (project_dir / "ghdtk.toml").write_text(
        'github_token = "file_token"\n'
        'github_base_url = "https://github.enterprise.local/api/v3"\n'
        "analysis_minimum_stars = 25\n",
        encoding="utf-8",
    )
    settings = load_settings()
    assert settings.github_token.get_secret_value() == "file_token"
    assert settings.github_base_url == "https://github.enterprise.local/api/v3"
    assert settings.analysis_minimum_stars == 25
    assert settings.cache_ttl_seconds == 86_400


def test_extra_file_keys_ignored(project_dir: Path) -> None:
    (project_dir / "ghdtk.toml").write_text(
        'github_token = "token"\nsome_future_key = true\n', encoding="utf-8"
    )
    assert load_settings().github_token.get_secret_value() == "token"


def test_malformed_toml_raises(project_dir: Path) -> None:
    (project_dir / "ghdtk.toml").write_text("not [valid toml", encoding="utf-8")
    with pytest.raises(tomllib.TOMLDecodeError):
        load_settings()


def test_invalid_value_raises(project_dir: Path) -> None:
    (project_dir / "ghdtk.toml").write_text(
        'github_token = "token"\ngithub_max_retries = -1\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError):
        load_settings()


def test_invalid_collection_budget_raises(project_dir: Path) -> None:
    (project_dir / "ghdtk.toml").write_text(
        'github_token = "token"\ncollection_max_requests = 0\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError):
        load_settings()


# --- precedence ------------------------------------------------------------
# Highest first: env vars > .env > ghdtk.toml > defaults


def test_env_overrides_file(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (project_dir / "ghdtk.toml").write_text('github_token = "file_token"\n', encoding="utf-8")
    monkeypatch.setenv(_TOKEN, "env_token")
    assert load_settings().github_token.get_secret_value() == "env_token"


def test_dotenv_overrides_file(project_dir: Path) -> None:
    (project_dir / "ghdtk.toml").write_text('github_token = "file_token"\n', encoding="utf-8")
    (project_dir / ".env").write_text(f"{_TOKEN}=dotenv_token\n", encoding="utf-8")
    assert load_settings().github_token.get_secret_value() == "dotenv_token"


def test_env_overrides_dotenv(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (project_dir / ".env").write_text(f"{_TOKEN}=dotenv_token\n", encoding="utf-8")
    monkeypatch.setenv(_TOKEN, "env_token")
    assert load_settings().github_token.get_secret_value() == "env_token"


# --- config file resolution -------------------------------------------------


def test_resolve_config_path_none_when_missing(project_dir: Path) -> None:
    assert resolve_config_path() is None


def test_config_file_env_var(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    custom = project_dir / "custom.toml"
    custom.write_text('github_token = "custom_token"\n', encoding="utf-8")
    monkeypatch.setenv(_CONFIG_VAR, str(custom))
    assert load_settings().github_token.get_secret_value() == "custom_token"


def test_explicit_path_beats_env_var(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    a = project_dir / "a.toml"
    b = project_dir / "b.toml"
    a.write_text('github_token = "a"\n', encoding="utf-8")
    b.write_text('github_token = "b"\n', encoding="utf-8")
    monkeypatch.setenv(_CONFIG_VAR, str(b))
    assert load_settings(a).github_token.get_secret_value() == "a"


def test_missing_explicit_path_raises(project_dir: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_settings(project_dir / "nope.toml")


def test_missing_config_env_var_raises(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_CONFIG_VAR, str(project_dir / "nope.toml"))
    with pytest.raises(FileNotFoundError):
        load_settings()


# --- environment parsing ---------------------------------------------------


def test_env_bool_and_int_parsing(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_TOKEN, "token")
    monkeypatch.setenv("GHDTK_CACHE_ENABLED", "false")
    monkeypatch.setenv("GHDTK_ANALYSIS_MINIMUM_STARS", "42")
    settings = load_settings()
    assert settings.cache_enabled is False
    assert settings.analysis_minimum_stars == 42


def test_invalid_env_value_raises(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_TOKEN, "token")
    monkeypatch.setenv("GHDTK_GITHUB_TIMEOUT_SECONDS", "not-a-number")
    with pytest.raises(ValidationError):
        load_settings()


def test_settings_from_env_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_TOKEN, "token")
    settings = Settings()
    assert settings.github_token.get_secret_value() == "token"
