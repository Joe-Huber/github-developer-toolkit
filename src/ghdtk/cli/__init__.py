"""Command-line interface.

Reserved in this issue. Exposes version information and the ``config``
subcommand for inspecting resolved configuration; richer commands are built
out in later issues.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from ghdtk import __version__
from ghdtk.config import Settings, load_settings, resolve_config_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ghdtk",
        description="Analyze and improve your GitHub developer presence.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to a TOML config file (overrides GHDTK_CONFIG_FILE).",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("config", help="Inspect the resolved configuration.")
    return parser


def _cmd_config(settings: Settings, config_path: Path | None) -> int:
    print(f"config file: {config_path or '(none, defaults only)'}")
    print(f"github base url: {settings.github_base_url}")
    print(f"github timeout: {settings.github_timeout_seconds}s")
    print(f"github max retries: {settings.github_max_retries}")
    token = settings.github_token.get_secret_value()
    print(f"github token configured: {bool(token)}")
    print(
        f"cache: {'enabled' if settings.cache_enabled else 'disabled'} "
        f"(ttl={settings.cache_ttl_seconds}s)"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "config":
        try:
            settings = load_settings(args.config)
            config_path = resolve_config_path(args.config)
        except (ValidationError, FileNotFoundError) as exc:
            print(f"error: could not load configuration: {exc}", file=sys.stderr)
            return 1
        return _cmd_config(settings, config_path)
    return 0
