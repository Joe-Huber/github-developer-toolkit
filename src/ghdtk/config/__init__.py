"""Configuration module.

Public API: :class:`Settings` and :func:`load_settings`.
"""

from ghdtk.config.settings import (
    DEFAULT_CONFIG_FILE,
    ENV_CONFIG_FILE_VAR,
    Settings,
    load_settings,
    resolve_config_path,
)

__all__ = [
    "DEFAULT_CONFIG_FILE",
    "ENV_CONFIG_FILE_VAR",
    "Settings",
    "load_settings",
    "resolve_config_path",
]
