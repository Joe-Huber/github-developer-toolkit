"""Command-line interface.

Provides the ``analyze`` command that collects a GitHub profile, runs the
full analysis pipeline, and writes Markdown/JSON/HTML reports with clear
progress output, exit codes and error messages.

Exit codes:

- **0** — success
- **1** — general/unexpected error
- **2** — configuration error (missing token, invalid arguments)
- **3** — API error (authentication failure, rate limit, network)
- **4** — partial success (report generated but some collections failed)
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from pydantic import ValidationError

from ghdtk import __version__

# Exit codes
EXIT_SUCCESS = 0
EXIT_GENERAL = 1
EXIT_CONFIG = 2
EXIT_API = 3
EXIT_PARTIAL = 4

_FORMATS = ("md", "json", "html")


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

    analyze = subparsers.add_parser(
        "analyze",
        help="Analyze a GitHub profile and generate a report.",
    )
    analyze.add_argument("username", help="GitHub username to analyze.")
    analyze.add_argument(
        "-f",
        "--format",
        choices=_FORMATS,
        default="md",
        dest="output_format",
        help="Report output format (default: md).",
    )
    analyze.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output file path. Defaults to <username>.<ext> in the current directory.",
    )
    analyze.add_argument(
        "--max-requests",
        type=int,
        default=None,
        help="Maximum API requests for the collection run (default: from config).",
    )
    analyze.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Thread pool size for parallel collection, 1-32 (default: 1, sequential).",
    )
    analyze.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable the response cache for this run.",
    )
    analyze.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output: show per-collection timing and budget usage.",
    )
    analyze.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress progress output; only errors go to stderr.",
    )

    dashboard = subparsers.add_parser(
        "dashboard",
        help="Launch the interactive web dashboard.",
    )
    dashboard.add_argument("username", help="GitHub username to analyze and display.")
    dashboard.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for the dashboard server (default: 8000).",
    )
    dashboard.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for the dashboard server (default: 127.0.0.1).",
    )
    dashboard.add_argument(
        "--no-open",
        action="store_true",
        help="Don't automatically open the browser.",
    )
    dashboard.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output: show per-collection timing and budget usage.",
    )
    return parser


def _cmd_config(settings: object, config_path: Path | None) -> int:
    from ghdtk.config import Settings

    assert isinstance(settings, Settings)
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


def _emit(msg: str, *, quiet: bool = False, file: TextIO | None = None) -> None:
    if not quiet:
        print(msg, file=file if file is not None else sys.stderr)


def _cmd_analyze(args: argparse.Namespace) -> int:
    from ghdtk.api.client import GitHubClient
    from ghdtk.collectors.collectors import collect_profile_readme
    from ghdtk.collectors.orchestrator import collect_profile
    from ghdtk.config import load_settings
    from ghdtk.report.assemble import ReportAssembler
    from ghdtk.report.html import write_html
    from ghdtk.report.json import write_json
    from ghdtk.report.markdown import write_markdown

    quiet = args.quiet
    if args.verbose:
        from ghdtk.observability import configure_logging

        configure_logging()
    username: str = args.username
    output_format: str = args.output_format
    ext = {"md": "md", "json": "json", "html": "html"}[output_format]
    output_path: Path | None = args.output
    if output_path is None:
        output_path = Path(f"{username}.{ext}")

    # 1. Load settings
    _emit("[1/5] Loading configuration...", quiet=quiet)
    try:
        settings = load_settings(args.config)
    except (ValidationError, FileNotFoundError) as exc:
        print(f"error: configuration: {exc}", file=sys.stderr)
        return EXIT_CONFIG

    if args.no_cache:
        object.__setattr__(settings, "cache_enabled", False)

    if args.max_requests is not None:
        object.__setattr__(settings, "collection_max_requests", args.max_requests)
    if args.max_workers is not None:
        object.__setattr__(settings, "collection_max_workers", args.max_workers)

    # 2. Create client
    _emit("[2/5] Connecting to GitHub API...", quiet=quiet)
    try:
        client = GitHubClient.from_settings(settings)
    except Exception as exc:
        print(f"error: failed to create API client: {exc}", file=sys.stderr)
        return EXIT_CONFIG

    # 3. Collect profile
    _emit(f"[3/5] Collecting @{username}'s profile...", quiet=quiet)
    t0 = time.perf_counter()
    try:
        with client:
            snapshot = collect_profile(
                client,
                username,
                max_requests=settings.collection_max_requests,
                max_workers=settings.collection_max_workers,
            )
    except Exception as exc:
        _classify_api_error(exc)
        return EXIT_API
    collect_elapsed = time.perf_counter() - t0

    n_total = len(snapshot.collections)
    n_failed = sum(1 for r in snapshot.collections if r.status.value == "failed")
    n_skipped = sum(1 for r in snapshot.collections if r.status.value == "skipped")
    n_ok = n_total - n_failed - n_skipped

    if args.verbose:
        _emit(
            f"  collected {n_ok}/{n_total} collections "
            f"({n_failed} failed, {n_skipped} skipped) "
            f"in {collect_elapsed:.1f}s "
            f"({snapshot.budget_used}/{snapshot.budget_max} requests)",
            quiet=quiet,
        )
    else:
        status = "complete" if n_failed == 0 else "partial"
        _emit(
            f"  collection {status}: {n_ok}/{n_total} succeeded "
            f"({snapshot.budget_used}/{snapshot.budget_max} requests, "
            f"{collect_elapsed:.1f}s)",
            quiet=quiet,
        )

    # 4. Collect profile README
    _emit("[4/5] Analyzing profile...", quiet=quiet)
    try:
        with client:
            readme = collect_profile_readme(client, username, repositories=snapshot.repositories)
    except Exception:
        readme = None

    # 5. Assemble report
    now = datetime.now(UTC)
    report = ReportAssembler().assemble(
        username=username,
        snapshot=snapshot,
        now=now,
        profile_readme=readme,
    )

    # 6. Render and write
    _emit(f"[5/5] Rendering {output_format.upper()} report...", quiet=quiet)
    if output_format == "md":
        write_markdown(report, output_path)
    elif output_format == "json":
        write_json(report, output_path)
    elif output_format == "html":
        write_html(report, output_path)
    else:
        print(f"error: unknown format: {output_format}", file=sys.stderr)
        return EXIT_GENERAL

    _emit(f"  written to {output_path}", quiet=quiet)

    # Print overall score to stdout
    if report.profile.overall is not None:
        score = report.profile.overall.overall
        print(f"Overall score: {score:.0f}/100")

    if n_failed > 0:
        _emit(
            f"\nNote: {n_failed} collection(s) failed. Run with --verbose for details.",
            quiet=quiet,
        )
        return EXIT_PARTIAL

    return EXIT_SUCCESS


def _classify_api_error(exc: Exception) -> None:
    """Print a user-friendly message based on the exception type."""
    name = type(exc).__name__
    msg = str(exc)

    if "AuthenticationError" in name or "401" in msg:
        print(
            "error: authentication failed — check that GHDTK_GITHUB_TOKEN "
            "is set and the token has read access",
            file=sys.stderr,
        )
    elif "RateLimitError" in name or "403" in msg:
        print(
            "error: GitHub API rate limit exceeded — try again later or increase the token scope",
            file=sys.stderr,
        )
    elif "NotFoundError" in name or "404" in msg:
        print(f"error: user not found — @{msg.split()[-1] if msg else 'unknown'}", file=sys.stderr)
    else:
        print(f"error: API request failed ({name}): {msg}", file=sys.stderr)


def _cmd_dashboard(args: argparse.Namespace) -> int:
    """Launch the interactive web dashboard."""
    if args.verbose:
        from ghdtk.observability import configure_logging

        configure_logging()

    try:
        import uvicorn
    except ImportError:
        print(
            "error: dashboard requires extra dependencies.\n"
            "Install with: pip install 'ghdtk[dashboard]'",
            file=sys.stderr,
        )
        return EXIT_CONFIG

    from ghdtk.dashboard.app import create_app

    app = create_app()

    if not args.no_open:
        import webbrowser

        webbrowser.open(f"http://{args.host}:{args.port}")

    _emit(f"Dashboard serving @{args.username} at http://{args.host}:{args.port}", quiet=False)
    _emit("Press Ctrl+C to stop.", quiet=False)

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return EXIT_SUCCESS


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return EXIT_SUCCESS

    if args.command == "config":
        try:
            from ghdtk.config import load_settings, resolve_config_path

            settings = load_settings(args.config)
            config_path = resolve_config_path(args.config)
        except (ValidationError, FileNotFoundError) as exc:
            print(f"error: could not load configuration: {exc}", file=sys.stderr)
            return EXIT_CONFIG
        return _cmd_config(settings, config_path)

    if args.command == "analyze":
        return _cmd_analyze(args)

    if args.command == "dashboard":
        return _cmd_dashboard(args)

    return EXIT_SUCCESS
