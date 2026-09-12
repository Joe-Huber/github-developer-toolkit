# CLI Usage Guide

The `ghdtk` command-line tool collects a GitHub profile, runs the full analysis
pipeline, and writes Markdown, JSON, or HTML reports.

## Installation

Requires Python 3.11+.

### With `uv` (recommended)

```bash
uv tool install git+https://github.com/Joe-Huber/github-developer-toolkit.git
```

This installs `ghdtk` as a standalone CLI tool in an isolated environment.
No conflicts with system packages.

### With `pipx`

```bash
pipx install git+https://github.com/Joe-Huber/github-developer-toolkit.git
```

### With `pip` (in a virtual environment)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install git+https://github.com/Joe-Huber/github-developer-toolkit.git
```

> **Note:** Modern macOS with Homebrew Python blocks `pip install` outside
> virtual environments (PEP 668). Use `uv`, `pipx`, or a venv instead.

## Quick Start

```bash
# Set your GitHub personal access token
export GHDTK_GITHUB_TOKEN="ghp_your_token_here"

# Analyze a profile — generates octocat.md
ghdtk analyze octocat

# JSON report
ghdtk analyze octocat -f json -o report.json

# HTML report
ghdtk analyze octocat -f html -o report.html
```

## Commands

### `ghdtk analyze`

Collect a GitHub profile and generate an analysis report.

```
ghdtk analyze <username> [OPTIONS]
```

| Option | Short | Description | Default |
|---|---|---|---|
| `--format` | `-f` | Output format: `md`, `json`, or `html` | `md` |
| `--output` | `-o` | Output file path | `<username>.<ext>` |
| `--max-requests` | | Maximum API requests for collection | From config |
| `--max-workers` | | Thread pool size (1-32) for parallel collection | `1` (sequential) |
| `--no-cache` | | Disable the response cache for this run | Off |
| `--verbose` | `-v` | Show per-collection timing and budget usage | Off |
| `--quiet` | `-q` | Suppress all progress output (errors only) | Off |
| `--config` | | Path to a TOML config file | Auto-detected |

**Examples:**

```bash
# Verbose run showing budget usage
ghdtk analyze octocat -v

# Quiet run with parallel collection
ghdtk analyze octocat -q --max-workers 4

# High-budget sequential run, no cache
ghdtk analyze octocat --max-requests 800 --no-cache
```

### `ghdtk config`

Inspect the resolved configuration.

```bash
ghdtk config
```

Outputs the active config file path, GitHub API settings, token status, and
cache configuration.

### `ghdtk --version`

Print the version and exit.

```bash
ghdtk --version
# ghdtk 0.1.0
```

## Token & Permissions

`ghdtk` is **read-only** — it never modifies any GitHub data. The token only
needs to read public profile data.

| Use case | Token type | Permissions |
|---|---|---|
| Public profiles only | Classic PAT | No scopes needed |
| Profiles with private repos | Classic PAT | `repo` scope |
| Public profiles only | Fine-grained PAT | See permissions below |
| Profiles with private repos | Fine-grained PAT | Same repo permissions, scoped to the repos |

**Classic PAT**: create at <https://github.com/settings/tokens>. No scopes
needed for public data; add the `repo` scope if you want private repositories
included in the analysis. Classic PATs are not subject to fine-grained
permission checks, but GitHub still restricts stargazer listings (see below).

**Fine-grained PAT**: create at
<https://github.com/settings/personal-access-tokens/new>. Grant the following
permissions:

- Repository access: select the repositories to analyze (or "All repositories")
- Repository permissions:
  - `Metadata` (Read-only) — required for all repository endpoints
  - `Contents` (Read-only) — commits, README, and language stats
  - `Pull requests` (Read-only)
  - `Issues` (Read-only)
- User permissions:
  - `Starring` (Read) — required for stargazer timelines
  - `Following` (Read) — followers/following analysis

**Stargazer timelines**: since July 2026, GitHub limits the stargazer listing
endpoints to the repository's admins and collaborators. Star-growth analysis
therefore works only for repositories the token owner owns or collaborates on;
for other users' profiles these requests fail with `404 Not Found` regardless of
token permissions, and the `star_growth.insufficient_data` finding is drawn.

**Rate limits**: an unauthenticated token gets 60 requests/hour.
Any valid token raises this to 5,000 requests/hour. The tool defaults to
a budget of 500 requests per profile run.

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success — report written |
| `1` | General/unexpected error |
| `2` | Configuration error — missing token, invalid config file, bad arguments |
| `3` | API error — authentication failure, rate limit, network timeout |
| `4` | Partial success — report generated but some collections failed |

## Configuration

`ghdtk` reads settings from multiple sources with documented precedence
(highest wins):

1. **Command-line flags** (`--max-requests`, `--no-cache`, etc.)
2. **Environment variables** (prefix `GHDTK_`)
3. **Config file** (`ghdtk.toml` in the working directory or `$GHDTK_CONFIG_FILE`)

### Key Environment Variables

| Variable | Description | Default |
|---|---|---|
| `GHDTK_GITHUB_TOKEN` | GitHub personal access token | *Required* |
| `GHDTK_GITHUB_BASE_URL` | GitHub API base URL | `https://api.github.com` |
| `GHDTK_CACHE_ENABLED` | Enable response caching (`true`/`false`) | `true` |
| `GHDTK_CACHE_TTL_SECONDS` | Cache time-to-live in seconds | `86400` (24h) |
| `GHDTK_COLLECTION_MAX_REQUESTS` | API request budget | `500` |
| `GHDTK_COLLECTION_MAX_WORKERS` | Parallel collection threads | `1` |

### Config File Example

```toml
github_token = "ghp_..."
github_base_url = "https://api.github.com"
cache_enabled = true
cache_ttl_seconds = 86400
collection_max_requests = 500
```

## Output Formats

### Markdown (`-f md`)

Human-readable report with sections for each analysis dimension, scores,
metrics, and recommendations.  Starts with a heading `# GitHub Profile Report: <username>`.

### JSON (`-f json`)

Machine-readable JSON conforming to the `Report` schema.  Includes the full
analysis tree: profile data, per-dimension analyses, overall score, metrics,
and synthesis.

### HTML (`-f html`)

Styled single-file HTML report suitable for sharing or hosting.  Contains the
same information as the Markdown report with CSS styling.
