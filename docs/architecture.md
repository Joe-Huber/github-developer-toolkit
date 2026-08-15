# Architecture Overview

This document describes the module boundaries and data flow of the GitHub
Developer Toolkit, and the core architectural principles every feature must
follow. It corresponds to issue #12 (Epic — Project Foundation & Core
Architecture).

## Architectural principles

1. **Strict separation of raw and derived data.** Raw GitHub data is the single
   source of truth and is never modified, analyzed, or annotated in place.
   Everything computed from it lives in the derived layer and references its
   raw inputs.

2. **Explainable scoring.** Every metric, score component, finding and
   recommendation carries provenance pointing at the exact raw data that
   produced it, plus the rationale/formula behind it. A report must be
   answerable: *"why did I get this score?"*.

3. **Reproducibility.** The same raw snapshot fed through the same pipeline
   version yields the same report. No randomness, no wall-clock dependence in
   computations; timestamps are recorded as analysis metadata, not inputs.

4. **Extensibility.** New raw entities, analyzers, dimensions or
   recommendations slot into well-defined seams without touching existing
   models or the CLI.

5. **The data layer is agnostic to the analysis layer.** `ghdtk.models.raw`
   contains zero analysis logic; the derived layer depends only on the raw
   model surface it needs.

## Module layout

```
src/ghdtk/
├── api/              # GitHub API client (auth, retries, rate limits)
├── models/
│   ├── raw/          # immutable snapshots of GitHub API payloads (#14)
│   └── derived/      # metrics, scores, findings, recommendations, report (#15)
├── collectors/       # fetch API data -> raw snapshots
├── analyzers/        # raw snapshots -> metrics & findings
├── scoring/          # metrics -> dimension scores
├── recommendations/  # findings -> recommendations
├── report/           # analysis -> report DTO / JSON
├── config/           # configuration: file + env + defaults (#13)
└── cli/              # command-line interface
```

## Data flow

```
GitHub API
   │
   ▼
api/            requests with auth/retry, returns payloads
   │
   ▼
collectors/     deserialize payloads into immutable raw snapshots
   │
   ▼
models/raw      source of truth — frozen, faithful, never modified
   │
   ▼
analyzers/      compute metrics + findings (each carries provenance)
   │
   ▼
models/derived  MetricRecord, Finding
   │
   ▼
scoring/        combine metrics into DimensionScore with breakdown
   │
   ▼
models/derived  DimensionScore
   │
   ▼
recommendations/  findings -> prioritized Recommendation
   │
   ▼
report/         assemble ProfileAnalysis + Report DTO -> JSON
```

The pipeline is strict **raw → derived**: `api/` and `collectors/` never read
derived data, `analyzers/` and everything downstream never touch the network
or the raw payloads' representation, and `models/raw` is never mutated.

## Raw data layer (`models/raw`)

- **Immutable:** every raw model is `frozen=True`; a snapshot cannot be
  changed after deserialization.
- **Faithful:** field names mirror the GitHub REST/GraphQL payloads actually
  used. GraphQL-only payloads (e.g. the contribution calendar) alias their
  camelCase fields.
- **Lossless for missing data:** optional fields default to `None` — an absent
  boolean stays `None`, it is never fabricated as `False`.
- **Tolerant of unknown fields:** `extra="ignore"` drops fields the product
  does not model yet without raising.

Deserialization of any fetchable payload (issue #16) must never raise on
missing/extra fields; invalid *types* still raise, surfacing real problems.

## Collection pipeline (`collectors`)

- `ghdtk.collectors.collectors` — thin collectors, one per resource (user,
  repositories, languages, readme, commits, pull requests, issues, followers,
  following, stargazers, contribution calendar), returning raw typed payloads.
- `ghdtk.collectors.orchestrator.collect_profile` — schedules collectors by
  dependency and priority: core profile (user, repositories, contribution
  calendar, followers, following) → per-repository metadata for repos sorted by
  stars → the stargazer timeline for the most-starred **owned** (non-fork)
  repository, recorded under `stargazers:<full_name>`. Sequencing is
  sequential.
- `ghdtk.collectors.budget.CollectionBudget` — hard cap on requests per run
  (default 500, `collection_max_requests`). Paginated collections never exceed
  the remaining budget; collections that no longer fit are skipped with an
  explicit `budget_exhausted` status.
- `ProfileSnapshot` (`models/raw/profile.py`) — the run's container with a
  per-collection `CollectionRecord` (status, reason, detail, requests used).
  Runs never crash on partial failure: a failed collection is recorded and
  collection continues, so a snapshot is complete-but-possibly-partial
  (`snapshot.is_partial`).
- `ghdtk.collectors.collectors.collect_profile_readme` (issue #25) — retrieves
  the profile README from the `<username>/<username>` repository and returns a
  typed `ProfileReadme` that distinguishes *no profile repository*, *no
  README*, *empty README*, and *fetch failure* so analysis never has to guess
  why the markdown is absent.

## Analysis layer (`analyzers`)

Analyzers consume raw snapshots (or collection artifacts like `ProfileReadme`)
and produce derived `MetricRecord`s and `Finding`s (issue #23). They are pure:
no network access, no mutation of raw data, deterministic for a fixed input.

- `assess_profile_presence(user)` (issue #24) — per-field assessment of the
  presentation fields (name, bio, website, company, location, email, Twitter,
  hireable flag, account age). Each field is `present` / `missing` /
  `placeholder`, and findings carry the raw field they reference as evidence.
  Account age under 90 days and very short bios are flagged as quality
  signals. Output: `ProfilePresence`.
- `assess_readme_quality(profile_readme)` (issue #26) — structural signals of
  the profile README: word count, headings, code blocks, links, images,
  badges, structured sections (About / Skills / Contact), and personalization
  (username mentions, generic template wording). Findings reference the README
  and, where possible, the section or line (`content:section:about`,
  `content:line:3`) that produced them. Output: `ReadmeAssessment`.
- `ghdtk.analyzers.heuristics` — the shared placeholder/boilerplate matchers.
  Detection is deliberately conservative (obvious scaffold text such as
  `example.com`, `your company`, `lorem ipsum`, "welcome to my github
  profile"). It is a **documented heuristic, not a claim about intent**;
  matches are always attached to finding evidence so an analyst can judge
  them, and messages note the false-positive caveat (e.g. a company genuinely
  named "Example").
- `ghdtk.analyzers.thresholds.AnalysisThresholds` — the shared, validated
  configuration model for the analyzers (staleness window, minimum stars,
  minimum repositories, README length, standout and concentration thresholds,
  growth windows, follower-network lopsidedness). Defaults live in the model;
  tests override them directly so the analyzers stay deterministic and
  config-driven.
- `assess_repository_quality(snapshot, *, thresholds)` (issue #29) — per
  repository and portfolio quality signals: description presence (with
  placeholder detection via `heuristics`), README state (`present` /
  `absent` / `unknown`, where *absent* is only claimed when the `readme:<owner>/<repo>`
  collection record succeeded and *unknown* otherwise, so an unfetched README
  is never falsely reported missing), README length, topics, license and
  homepage. Portfolio coverage metrics (description/README/license/homepage)
  and low-coverage findings below `quality_coverage_threshold`. Output:
  `RepositoryQuality`.
- `assess_repository_activity(snapshot, *, now, thresholds)` (issue #30) —
  age, activity and consistency across the portfolio. Forks are counted but
  excluded from recency signals; archived repositories get an informational
  finding and are excluded from staleness; repositories without a push date
  are flagged `unknown`. Metrics cover active/dormant counts, median age and
  staleness, and 30/90/365-day recency buckets. Findings flag stale
  repositories, a portfolio with no recent activity, and multi-month
  inactivity. Output: `RepositoryActivity`.
- `assess_portfolio_composition(snapshot, *, now, thresholds)` (issue #31) —
  portfolio composition and standout identification. A standout is an owned,
  non-archived repository with at least `standout_star_threshold` stars pushed
  within `standout_active_days`. Star concentration (a single repository
  holding more than `concentration_top_share` of portfolio stars), fork ratio
  above `fork_ratio_threshold`, and a too-small portfolio
  (`minimum_repositories`) are reported as findings. Output:
  `PortfolioComposition`.
- `assess_star_distribution(snapshot, *, thresholds)` (issue #33) — star
  aggregation and distribution: total and per-repository stars, percentile
  distribution (p25/p50/p75/p90/p99), distribution buckets, and the
  most-starred ranking. All aggregates and the ranking are computed over
  **owned** repositories per the documented fork policy; fork stars are
  reported separately and a fork-star-share finding fires above
  `fork_ratio_threshold`. Output: `StarsAnalysis`.
- `assess_star_growth(snapshot, *, now, thresholds)` (issue #34) — star growth
  and trend from the stargazer timeline (with `starred_at`), which the
  collector fetches for the most-starred owned repository under
  `stargazers:<full_name>` with the shared page cap. The analyzer reports
  observed counts (stars in the last 30/90/365 days) as facts, but growth
  velocity and the rising/stable/slowing verdict are **only** drawn when the
  timeline covers the reported stargazer count and spans at least 30 days;
  otherwise the status is `insufficient` and a finding explains why. No
  history is ever claimed that was not observed. Output: `StarGrowthAnalysis`.
- `assess_follower_network(snapshot, *, thresholds)` (issue #36) — followers
  and network analysis. Counts and the followers-to-following ratio come from
  the raw user object (no extra API cost); a ratio at or above
  `network_lopsided_ratio` is an audience-driven profile, the reciprocal or
  below a network-driven one. When the follower list was collected (capped by
  the shared page cap), reach is reported as an **estimate**: the reported
  follower count carries a confidence equal to the observed coverage, and a
  partial sample fires a `partial_sample` finding so reach is never presented
  as the full audience. Mutual follows are computed from the collected
  follower/following samples (an estimate unless both lists fully cover their
  reported counts) and are `unavailable` when the following list was not
  collected. Growth history and org memberships are not exposed by the
  pipeline, so both report `unavailable` with a rationale — growth is never
  inferred. Output: `FollowerNetwork`.

## Derived data layer (`models/derived`)

- `MetricRecord` — id, label, value, **sources** (provenance), timestamp,
  confidence.
- `DimensionScore` + `ScoreBreakdown` — 0–100 score with weighted components,
  each component referencing the metric and raw inputs behind it.
- `Finding` — type, severity, evidence, recommendation references.
- `Recommendation` — priority, action, rationale, linked findings/metrics.
- `ProfileAnalysis` — snapshot container for one profile's analysis.
- `Report` — final serializable DTO.

All derived models serialize to JSON and round-trip losslessly.

## Configuration

Settings load from multiple sources in a documented precedence order
(highest first): command line (reserved) → environment variables (`GHDTK_*`)
→ `.env` → `ghdtk.toml` → defaults. See `src/ghdtk/config/` and
`.env.example`.

## Tooling & quality gates

- Package manager: **uv** (`uv sync`, `uv add`)
- Lint/format: **ruff**
- Type checking: **mypy** (strict, with the pydantic plugin)
- Tests: **pytest**
- One-command gate: **`make check`** (lint → format-check → typecheck → test)
- Pre-commit hooks run the same gates on every commit.

A clean checkout must pass `make check` before any work begins.
