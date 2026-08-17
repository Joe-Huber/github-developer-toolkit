<div align="center">
  <h1 align="center">GitHub Developer Toolkit :octocat: </h1>
  <p align="center">
    <a href="https://github.com/Joe-Huber/github-developer-toolkit/stargazers"><img src="https://img.shields.io/github/stars/Joe-Huber/github-developer-toolkit?style=for-the-badge" alt="GitHub stars"></a>
    <a href="https://github.com/Joe-Huber/github-developer-toolkit/network/members"><img src="https://img.shields.io/github/forks/Joe-Huber/github-developer-toolkit?style=for-the-badge" alt="GitHub forks"></a>
    <a href="https://github.com/Joe-Huber/github-developer-toolkit/issues"><img src="https://img.shields.io/github/issues/Joe-Huber/github-developer-toolkit?style=for-the-badge" alt="GitHub issues"></a>
  </p>
  <p align="center">
    <a href="https://github.com/Joe-Huber/github-developer-toolkit/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Joe-Huber/github-developer-toolkit?style=for-the-badge" alt="License"></a>
    <a href="https://github.com/Joe-Huber/github-developer-toolkit/pulls"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen?style=for-the-badge" alt="PRs Welcome"></a>
    <a href="https://github.com/Joe-Huber/github-developer-toolkit/commits/main"><img src="https://img.shields.io/github/last-commit/Joe-Huber/github-developer-toolkit?style=for-the-badge" alt="Last commit"></a>
  </p>
  <p align="center">
    An open-source system that helps developers improve, analyze, and showcase their GitHub presence.
  </p>
</div>

## Overview

The GitHub Developer Toolkit analyzes a developer's GitHub profile and turns
it into explainable metrics, dimension scores, findings, and actionable
recommendations. A core design principle is the strict separation between
**raw GitHub data** (the immutable source of truth) and **derived analysis**
(everything computed from it). See [docs/architecture.md](docs/architecture.md).

## Requirements

- [Python](https://www.python.org/) 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Make](https://www.gnu.org/software/make/) (optional, for the quality gates)
- A GitHub [Personal Access Token](https://github.com/settings/tokens) with
  read access to the data the analyzer fetches

## Setup

```sh
git clone https://github.com/Joe-Huber/github-developer-toolkit.git
cd github-developer-toolkit

# install the package and dev dependencies
uv sync

# configure the GitHub token
cp .env.example .env
# then edit .env and set GHDTK_GITHUB_TOKEN

# install the pre-commit hooks
uv run pre-commit install
```

Configuration loads from environment variables (`GHDTK_*`), a `.env` file, or
a `ghdtk.toml` config file, with documented precedence:
**env vars > `.env` > `ghdtk.toml` > defaults**.
See [.env.example](.env.example) for every available variable.

## Usage

```sh
# CLI entry point
uv run ghdtk --version
uv run ghdtk config          # inspect the resolved configuration
```

The profile-analysis commands are built out in later milestones; the data
models, configuration, and module boundaries are in place now.

## Architecture

The pipeline follows a strict **raw -> derived** flow. Raw GitHub data is
fetched, deserialized into immutable typed models, then analyzed into
explainable metrics, dimension scores, findings and recommendations. Every
score carries provenance pointing at the exact raw data that produced it.

```
GitHub API
   |
   v
api/             requests with auth/retry, returns payloads
   |
   v
collectors/      fetch API data -> immutable raw snapshots
   |
   v
models/raw       source of truth -- frozen, faithful, never modified
   |
   v
analyzers/       raw snapshots -> metrics + findings (each carries provenance)
   |
   v
scoring/         metrics -> dimension scores with weighted breakdown
   |
   v
recommendations/ findings -> actionable, prioritized recommendations
   |
   v
report/          analysis -> Report DTO -> JSON / Markdown / HTML
```

### Module-to-epic mapping

| Module | Epic / Issue | Description |
|---|---|---|
| `api/` | #18 — API client | Auth, retries, rate limiting, response caching |
| `models/raw/` | #14 — Raw data models | Frozen Pydantic models mirroring GitHub payloads |
| `models/derived/` | #15 — Derived data models | MetricRecord, Finding, DimensionScore, Recommendation |
| `collectors/` | #22 — Collection pipeline | Orchestrates data fetching with budget and parallelism (#63) |
| `analyzers/` | #23 — Analyzers | 16 analyzers producing metrics and findings |
| `scoring/` | #46 — Scoring framework | 8 dimension scorers with weighted aggregation |
| `recommendations/` | #51 — Recommendations | Rule-based engine producing actionable items |
| `report/` | #54 — Report layer | Markdown, JSON and HTML renderers |
| `config/` | #13 — Configuration | Settings from env vars, `.env` and `ghdtk.toml` |
| `observability/` | #65 — Observability | Structured logging, correlation ids, run metrics |

### Key resources

- **Methodology & scoring**: [docs/methodology.md](docs/methodology.md) --
  how every metric is computed, how scores are weighted, what the thresholds
  mean, and what data limitations exist.
- **Architecture deep-dive**: [docs/architecture.md](docs/architecture.md) --
  module boundaries, data flow, design principles, all analyzer descriptions.
- **Testing strategy**: [docs/testing.md](docs/testing.md) -- fixture corpus,
  deterministic replay, coverage gate.
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md) -- dev setup, quality
  gates, configuration reference.

## Quality gates

Every change must pass all gates:

```sh
make check       # lint + format-check + typecheck + test
```

Individual gates:

```sh
make lint        # ruff check
make format      # ruff format (auto-fix)
make format-check
make typecheck   # mypy (strict)
make test        # pytest
make coverage    # pytest with coverage report
```

The pre-commit hooks run the same checks automatically on every commit.

## Project structure

```
src/ghdtk/
├── api/              # GitHub API client
├── models/
│   ├── raw/          # immutable snapshots of GitHub payloads
│   └── derived/      # metrics, scores, findings, recommendations, report
├── collectors/       # fetch API data → raw snapshots
├── analyzers/        # raw snapshots → metrics & findings
├── scoring/          # metrics → dimension scores
├── recommendations/  # findings → recommendations
├── report/           # analysis → report DTO
├── config/           # configuration (file + env + defaults)
├── observability/    # structured logging, correlation ids, run metrics
└── cli/              # command-line interface
```

## Contributing

PRs are welcome. Before opening one, make sure `make check` passes and the
pre-commit hooks are green. See [CONTRIBUTING.md](CONTRIBUTING.md) for dev
setup, quality gates, configuration reference, and issue/PR conventions.
See [docs/architecture.md](docs/architecture.md) for the design principles
every contribution should follow.

## License

[MIT](LICENSE)
