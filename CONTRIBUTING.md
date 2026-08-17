# Contributing to github-developer-toolkit

Thank you for your interest in contributing. Pull requests are welcome. All
changes must pass every quality gate before merging.

---

## Development Setup

### Prerequisites

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/) (package manager and virtual-environment tool)

### Clone and install

```sh
git clone https://github.com/Joe-Huber/github-developer-toolkit.git
cd github-developer-toolkit

# Install the package and dev dependencies
uv sync

# Configure the GitHub token
cp .env.example .env
# Edit .env and set GHDTK_GITHUB_TOKEN

# Install pre-commit hooks
uv run pre-commit install
```

A GitHub Personal Access Token is required for live runs. `ghdtk` is
read-only — any valid token works for public profiles; add the `repo`
scope to include private repositories. Tokens are never needed for tests,
which use a recorded-response corpus.

---

## Quality Gates

Every change must pass all gates before merging.

```sh
make check       # lint + format-check + typecheck + test
```

Individual gates:

| Command          | Tool                     | What it checks                              |
| ---------------- | ------------------------ | ------------------------------------------- |
| `make lint`      | ruff check               | Linting (unused imports, style)             |
| `make format`    | ruff format              | Auto-format code                            |
| `make format-check` | ruff format --check   | Verify formatting without modifying files   |
| `make typecheck` | mypy (strict)            | Static type checking                        |
| `make test`      | pytest                   | Run the test suite                          |
| `make coverage`  | pytest + coverage        | Coverage report (95 % floor)                |

Pre-commit hooks run the same checks on every commit automatically. If a hook
fails the commit is blocked until the issue is fixed.

---

## Running Tests

```sh
make test                        # run all tests
make coverage                    # run with coverage report
uv run pytest tests/api/         # run a specific test directory
uv run pytest -k test_name       # run a specific test by name
```

Tests never call the live GitHub API. The collection pipeline is exercised
through a recorded-response corpus under `tests/fixtures/corpus/`. See
`docs/testing.md` for the corpus format and how to extend it.

---

## Project Structure

```
src/ghdtk/
├── api/              # GitHub API client (auth, retries, rate limits)
├── models/
│   ├── raw/          # immutable snapshots of GitHub payloads
│   └── derived/      # metrics, scores, findings, recommendations, report
├── collectors/       # fetch API data -> raw snapshots
├── analyzers/        # raw snapshots -> metrics & findings
├── scoring/          # metrics -> dimension scores
├── recommendations/  # findings -> recommendations
├── report/           # analysis -> report DTO / JSON
├── config/           # configuration (file + env + defaults)
├── observability/    # structured logging, correlation ids, run metrics
└── cli/              # command-line interface

tests/
├── fixtures/         # recorded-response corpus for deterministic testing
├── api/              # API client and normalizer tests
├── collectors/       # collector and orchestrator tests
├── analyzers/        # analyzer tests
├── scoring/          # scorer tests
├── report/           # renderer and golden-file tests
├── observability/    # logging and metrics tests
└── ...
```

---

## Architecture Principles

Every contribution must follow these principles. See `docs/architecture.md`
for full details.

1. **Strict separation of raw and derived data.** Raw GitHub data is never
   modified, analyzed, or annotated in place.
2. **Explainable scoring.** Every metric, score, finding, and recommendation
   carries provenance.
3. **Reproducibility.** The same raw snapshot yields the same report. No
   randomness, no wall-clock dependence in computations.
4. **Extensibility.** New analyzers, scorers, and recommendations slot into
   well-defined seams.
5. **The data layer is agnostic to the analysis layer.**

---

## Contribution Workflow

### Branching

- Create a feature branch from `main`:

  ```sh
  git checkout -b feat/issue-N-description
  ```

- Reference the issue number in the branch name and commit message.

### Commit messages

- Reference the issue number: `Fix: description (#N)` or `Feat: description (#N)`
- Keep commits focused: one logical change per commit.
- Pre-commit hooks must pass on every commit.

### Pull requests

- Target `main`.
- PR description should reference the issue: `Closes #N`.
- All quality gates must pass in CI.
- At least one review is required before merging.

### Issue labels

The repository uses these labels for documentation issues:

| Label              | Meaning                      |
| ------------------ | ---------------------------- |
| `type: documentation` | Documentation request     |
| `part of: #66`     | Part of the documentation epic |

---

## Configuration Reference

All configuration is loaded from environment variables (prefixed `GHDTK_`),
a `.env` file, or a `ghdtk.toml` config file. Precedence (highest wins):

**env vars > `.env` > `ghdtk.toml` > built-in defaults**

Example `ghdtk.toml`:

```toml
github_token = "ghp_..."
github_base_url = "https://api.github.com"
cache_ttl_seconds = 43200
analysis_minimum_stars = 25
```

### GitHub API

| Setting               | Env var                         | Default                      | Description                                                 |
| --------------------- | ------------------------------- | ---------------------------- | ----------------------------------------------------------- |
| `github_token`        | `GHDTK_GITHUB_TOKEN`           | *(required)*                 | GitHub Personal Access Token                                |
| `github_base_url`     | `GHDTK_GITHUB_BASE_URL`        | `https://api.github.com`     | API endpoint (override for GitHub Enterprise)               |
| `github_timeout_seconds` | `GHDTK_GITHUB_TIMEOUT_SECONDS` | `30`                       | Per-request timeout in seconds                              |
| `github_max_retries`  | `GHDTK_GITHUB_MAX_RETRIES`     | `3`                          | Maximum retries on transient errors                         |
| `github_per_page`     | `GHDTK_GITHUB_PER_PAGE`        | `100`                        | Page size for paginated endpoints (1--100)                  |

### Caching

| Setting            | Env var                        | Default  | Description                                |
| ------------------ | ------------------------------ | -------- | ------------------------------------------ |
| `cache_enabled`    | `GHDTK_CACHE_ENABLED`         | `true`   | Enable or disable response caching         |
| `cache_ttl_seconds`| `GHDTK_CACHE_TTL_SECONDS`     | `86400`  | Cache time-to-live in seconds (24 hours)   |
| `cache_dir`        | `GHDTK_CACHE_DIR`             | `None`   | Directory for on-disk cache (optional)     |

### Collection Pipeline

| Setting                  | Env var                             | Default | Description                                            |
| ------------------------ | ----------------------------------- | ------- | ------------------------------------------------------ |
| `collection_max_requests`| `GHDTK_COLLECTION_MAX_REQUESTS`    | `500`   | Hard cap on API requests per run                       |
| `collection_max_workers` | `GHDTK_COLLECTION_MAX_WORKERS`     | `1`     | Thread pool size for parallel collection (1--32; 1 = sequential) |

### Analysis Thresholds

| Setting                      | Env var                                  | Default | Description                                      |
| ---------------------------- | ---------------------------------------- | ------- | ------------------------------------------------ |
| `analysis_minimum_stars`     | `GHDTK_ANALYSIS_MINIMUM_STARS`          | `10`    | Star count for standout detection                |
| `analysis_minimum_commits`   | `GHDTK_ANALYSIS_MINIMUM_COMMITS`        | `5`     | Minimum commits for activity analysis            |
| `analysis_minimum_repositories` | `GHDTK_ANALYSIS_MINIMUM_REPOSITORIES` | `3`     | Minimum repository count                         |
| `analysis_readme_min_chars`  | `GHDTK_ANALYSIS_README_MIN_CHARS`       | `100`   | README length threshold                          |
| `analysis_staleness_days`    | `GHDTK_ANALYSIS_STALENESS_DAYS`         | `90`    | Days without a push to flag a repo as stale      |

### Scoring

| Setting                       | Env var                                    | Default | Description                                        |
| ----------------------------- | ------------------------------------------ | ------- | -------------------------------------------------- |
| `scoring_cadence_target`      | `GHDTK_SCORING_CADENCE_TARGET`            | `4.0`   | Target commits per month                           |
| `scoring_gap_good_days`       | `GHDTK_SCORING_GAP_GOOD_DAYS`             | `14`    | Max days without commits to be "active"            |
| `scoring_gap_bad_days`        | `GHDTK_SCORING_GAP_BAD_DAYS`              | `60`    | Days without commits to flag a long gap            |
| `scoring_strength_threshold`  | `GHDTK_SCORING_STRENGTH_THRESHOLD`        | `70.0`  | Score at or above which a dimension is a strength  |
| `scoring_weakness_threshold`  | `GHDTK_SCORING_WEAKNESS_THRESHOLD`        | `40.0`  | Score at or below which a dimension is a weakness  |

---

## Type Checking

The project uses mypy in **strict** mode with the pydantic plugin. All new code
must be fully typed. Key patterns:

- Use `from __future__ import annotations` in every module.
- Prefer `str | None` over `Optional[str]`.
- Use `TypeVar` for generic functions.
- Pydantic models use `model_config = ConfigDict(frozen=True)` for immutability.

---

## Documentation

- Architecture: `docs/architecture.md`
- Testing strategy: `docs/testing.md`
- Methodology and scoring: `docs/methodology.md`
- Configuration reference: this file (Configuration Reference section above)
