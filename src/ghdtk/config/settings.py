"""Application configuration.

Loads settings from multiple sources with a documented precedence
(highest wins first):

1. Command line (future; reserved in the CLI layer)
2. Environment variables (prefix ``GHDTK_``)
3. ``.env`` file in the working directory
4. TOML config file (``ghdtk.toml`` by default)
5. Built-in defaults

Config file resolution order:

- explicit path passed to :func:`load_settings`
- ``GHDTK_CONFIG_FILE`` environment variable
- ``ghdtk.toml`` in the current working directory

Example ``ghdtk.toml``::

    github_token = "ghp_..."
    github_base_url = "https://api.github.com"
    cache_ttl_seconds = 43200
    analysis_minimum_stars = 25

Invalid values raise :class:`pydantic.ValidationError`; a missing config file
raises :class:`FileNotFoundError`; a malformed file raises
:class:`tomllib.TOMLDecodeError`.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

DEFAULT_CONFIG_FILE = "ghdtk.toml"
ENV_CONFIG_FILE_VAR = "GHDTK_CONFIG_FILE"

# Path of the active config file, installed only for the duration of a
# Settings construction. Consumed by ``Settings.settings_customise_sources``
# so the TOML values land below env vars in precedence.
_config_file_override: Path | None = None
_config_lock = threading.Lock()


class Settings(BaseSettings):
    """Runtime configuration for the analyzer.

    Fields are intentionally flat so that environment variable names
    (``GHDTK_GITHUB_TOKEN``) and config file keys (``github_token``) map 1:1.
    """

    model_config = SettingsConfigDict(
        env_prefix="GHDTK_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- GitHub API -----------------------------------------------------
    github_token: SecretStr
    github_base_url: str = "https://api.github.com"
    github_timeout_seconds: float = Field(default=30.0, gt=0)
    github_max_retries: int = Field(default=3, ge=0)
    github_per_page: int = Field(default=100, ge=1, le=100)

    # --- Caching --------------------------------------------------------
    cache_enabled: bool = True
    cache_ttl_seconds: int = Field(default=86_400, ge=0)
    cache_dir: Path | None = None

    # --- Collection pipeline --------------------------------------------
    collection_max_requests: int = Field(default=500, ge=1)
    collection_max_workers: int = Field(default=1, ge=1, le=32)

    # --- Analysis thresholds --------------------------------------------
    analysis_minimum_stars: int = Field(default=10, ge=0)
    analysis_minimum_commits: int = Field(default=5, ge=0)
    analysis_minimum_repositories: int = Field(default=3, ge=0)
    analysis_readme_min_chars: int = Field(default=100, ge=0)
    analysis_staleness_days: int = Field(default=90, ge=0)

    # --- Scoring --------------------------------------------------------
    scoring_cadence_target: float = Field(default=4.0, ge=0.0)
    scoring_gap_good_days: int = Field(default=14, ge=1)
    scoring_gap_bad_days: int = Field(default=60, ge=1)
    scoring_strength_threshold: float = Field(default=70.0, ge=0.0, le=100.0)
    scoring_weakness_threshold: float = Field(default=40.0, ge=0.0, le=100.0)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Order sources by priority: init, env, dotenv, secrets, TOML file."""
        from pydantic_settings import TomlConfigSettingsSource

        sources: tuple[PydanticBaseSettingsSource, ...] = (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )
        with _config_lock:
            path = _config_file_override
        if path is not None:
            sources = (
                *sources,
                TomlConfigSettingsSource(settings_cls, toml_file=path),
            )
        return sources


def resolve_config_path(explicit: Path | None = None) -> Path | None:
    """Resolve the config file path, or ``None`` if no file is configured."""
    if explicit is not None:
        if not explicit.is_file():
            raise FileNotFoundError(f"Config file not found: {explicit}")
        return explicit

    env_path = os.environ.get(ENV_CONFIG_FILE_VAR)
    if env_path:
        path = Path(env_path).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Config file from {ENV_CONFIG_FILE_VAR} not found: {path}")
        return path

    default = Path(DEFAULT_CONFIG_FILE)
    return default if default.is_file() else None


def load_settings(config_path: Path | None = None) -> Settings:
    """Load settings, applying config-file values underneath env vars.

    Precedence: env vars > ``.env`` file > TOML config file > defaults.
    """
    path = resolve_config_path(config_path)

    global _config_file_override
    with _config_lock:
        _config_file_override = path
    try:
        return Settings()
    finally:
        with _config_lock:
            _config_file_override = None
