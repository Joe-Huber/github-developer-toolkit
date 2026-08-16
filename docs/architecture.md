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
report/         assemble Report DTO -> JSON / Markdown / HTML
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
  The cross-repository PR/issue collectors (`collect_pull_request_search`,
  `collect_issue_search`, issue #40) use the search API with
  `author:<username> type:pr` / `author:<username> type:issue` queries and
  return issue-shaped search items; PR items have their nested `pull_request`
  fields (`merged`, `merged_at`, `review_comments`) lifted by the client before
  they parse into `PullRequest`.
- `ghdtk.collectors.orchestrator.collect_profile` — schedules collectors by
  dependency and priority: core profile (user, repositories, contribution
  calendar, followers, following) → cross-repository PR and issue collections
  (`pull_requests:search`, `issues:search`) → per-repository metadata for repos
  sorted by stars → the stargazer timeline for the most-starred **owned**
  (non-fork) repository, recorded under `stargazers:<full_name>`. Sequencing is
  sequential.
- `ghdtk.collectors.budget.CollectionBudget` — hard cap on requests per run
  (default 500, `collection_max_requests`). Paginated collections never exceed
  the remaining budget; collections that no longer fit are skipped with an
  explicit `budget_exhausted` status.
- `ProfileSnapshot` (`models/raw/profile.py`) — the run's container with a
  per-collection `CollectionRecord` (status, reason, detail, requests used).
  Runs never crash on partial failure: a failed collection is recorded and
  collection continues, so a snapshot is complete-but-possibly-partial
  (`snapshot.is_partial`). Cross-repository search collections are stored on
  the snapshot as `search_pull_requests` and `search_issues` flat lists
  (issue #40); per-repository lists remain under `pull_requests` / `issues`
  keyed by repository.
- `ghdtk.collectors.collectors.collect_profile_readme` (issue #25) — retrieves
  the profile README from the `<username>/<username>` repository and returns a
  typed `ProfileReadme` that distinguishes *no profile repository*, *no
  README*, *empty README*, and *fetch failure* so analysis never has to guess
  why the markdown is absent.
- Contribution calendar retrieval (issue #39) — `collect_contribution_calendar`
  fetches the calendar via GraphQL
  (`user.contributionsCollection.contributionCalendar`), including
  `restrictedContributionsCount` so hidden/private contributions can be
  disclosed. The documented fallback is honest: when the GraphQL collection
  fails or is skipped, the calendar analysis reports `unavailable` rather than
  guessing.

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
  growth windows, follower-network lopsidedness, commit/contribution gaps and
  streaks, external-engagement shares for PRs and issues, review/comment
  participation shares, the minimum months/issues before a trend is reported,
  language concentration and diversity thresholds, and the technology-domain
  mapping coverage / specialization / diversity thresholds). Defaults live in
  the model; tests override them directly so the analyzers stay deterministic
  and config-driven.
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
- `assess_commit_activity(snapshot, *, thresholds)` (issue #38) — commit
  history & activity. Coverage is explicit: GitHub's commit *search* API caps
  results around 1000 and is not used; commits are collected per repository
  (author-filtered listing) within the shared page cap and request budget, so
  the results are a window, never a complete lifetime history. Metrics cover
  frequency (commits per month), consistency (active days, median and longest
  gaps), per-repository breakdown, and timing patterns (weekday / hour of day
  from the author date). The coverage window finding states the observed
  date span, long gaps fire above `commit_gap_days`, and a cadence at or
  above `commit_cadence_per_month` is reported as consistent. Commits without
  an author date are counted but disclosed, and time-based metrics report
  `unavailable` rather than inventing a window. Output: `CommitActivity`.
- `assess_contribution_calendar(snapshot, *, thresholds)` (issue #39) — the
  GraphQL contribution calendar quantified: totals, active days, activity
  density, current/longest streaks, longest inactive run, and yearly/monthly
  patterns. Streaks are run-lengths over the returned calendar window.
  Private/hidden contributions are disclosed via
  `restrictedContributionsCount` (fetched alongside the calendar), never
  assumed; notable streaks fire at or above `streak_notable_days` and long
  inactive runs at or above `contribution_gap_days`. When the calendar was
  not collected the analysis reports `unavailable` with a rationale.
  Output: `ContributionCalendarAnalysis`.
- `assess_pull_request_collaboration(snapshot, *, thresholds)` (issue #41) —
  pull request health & collaboration from the cross-repository search
  collection (`search_pull_requests`, query `author:<username> type:pr`).
  Metrics cover total / merged / open / closed / closed-unmerged counts, merge
  rate (share of resolved PRs merged), median time to merge (only where
  `merged_at` is derivable), external-repository share, repository diversity,
  and review participation measured through review-comment counts (search
  results expose counts, not reviewer identities). A repository is "external"
  when it is not one of the profile's own repositories in the snapshot; items
  that name no repository are disclosed, never guessed. External engagement
  fires at or above `pr_external_share` and review collaboration at or above
  `pr_reviewed_share`. The coverage-window finding states the observed date
  span and the search-API/request-budget cap. Output: `PullRequestAnalysis`.
- `assess_issue_participation(snapshot, *, thresholds)` (issue #42) — issue
  participation from the cross-repository search collection (`search_issues`,
  query `author:<username> type:issue`). Metrics cover open/closed counts and
  close rate, median time to close and oldest open age, comment participation
  (via the issue `comments` count), external-repository share and repository
  diversity, and a monthly opened/closed breakdown. Activity trends are
  reported **only where the data supports them**: a rising/slowing direction
  is drawn only when the issues span at least `issue_trend_min_months` distinct
  months and at least `issue_trend_min_issues` total issues (recent activity
  months vs earlier ones against `trend_rising_ratio` /
  `trend_slowing_ratio`); otherwise the monthly breakdown is still reported and
  an informational finding explains why no trend is claimed. Output:
  `IssueParticipationAnalysis`.
- `assess_language_distribution(snapshot, *, thresholds)` (issue #44) — the
  portfolio's language distribution and primary languages, computed from the
  per-repository language byte statistics collected under
  `languages:<full_name>`. Weighting is byte-based: each language's share is
  its bytes over the total bytes across every repository with byte statistics,
  so larger repositories contribute proportionally more. Each repository's
  primary language is the largest in its statistics; repositories without byte
  statistics fall back to the declared `language` field (reported with
  `has_byte_stats=False`), and repositories with neither are disclosed as
  unknown, never guessed. Empty statistics mean no detectable code. A dominant
  language at or above `language_concentration_threshold` fires a concentration
  finding, and `language_distinct_threshold` or more distinct languages fire a
  polyglot standout; missing data is surfaced in a coverage finding. Output:
  `LanguageDistributionAnalysis`.
- `assess_technology_diversity(snapshot, *, thresholds, domain_map)` (issue
  #45) — technology diversity and dominant-area analysis from language and
  topic evidence only. Technology names map to domains (web, data, mobile,
  infrastructure, backend) through `DEFAULT_DOMAIN_MAP`, a documented and
  configurable mapping (`domain_map` overrides it per call; lookups are
  case-insensitive because topics are lowercase). Domain shares are
  byte-weighted like the language distribution; a domain's share is its bytes
  over the mapped bytes, and unmapped languages accumulate into
  `unmapped_share` and are disclosed, never guessed. Diversity is the Simpson
  index `1 - sum(p_i^2)` over the mapped domain shares. Repository topics that
  match the mapping corroborate as per-domain presence counts but do not
  re-weight the index. Specialization fires when the top domain's share reaches
  `technology_specialization_threshold`, broad coverage when the index reaches
  `technology_diversity_threshold`, and low mapping coverage below
  `technology_mapping_coverage_threshold` is disclosed. Output:
  `TechnologyDiversityAnalysis`.

## Scoring layer (`scoring/`)

Combines the derived analyses into explainable 0–100 dimension scores and an
overall profile score (issues #46–#50). Every score is built from the raw or
derived values that produced it and exposes them as evidence, so nothing is
scored from data that was not collected.

- **Framework & normalization** (issue #47) — the `Scorer` protocol,
  `ScoreInputs` (one container of analyzer outputs), the `ScoringRegistry`
  (runs a collection of scorers, skipping any that report no evidence) and the
  configurable `ScoringConfig` (per-dimension weights, normalization targets,
  strength/weakness thresholds, loaded via `ScoringConfig.from_settings` from
  the `scoring_*` settings). Normalization helpers are `clamp`,
  `normalize_ratio`, `normalize_linear` (invertible), `normalize_log` and
  `blend`; `blend` returns each component's normalized weight and contribution
  so the contributions sum exactly to the dimension score. Edge cases are
  explicit: out-of-range values clamp, degenerate ranges are defined, and no
  zero-division or `NaN` can leak into output.
- **Dimension scorers** (issues #48/#49) — eight registered scorers with
  documented, fixture-tested formulas. Scorers take only the analyzer outputs
  they need and return `None` (dimension unscorable) when required data is
  absent, so missing analyses never fabricate a score. Profile (from the
  profile presence/readme analyses), repository/code quality (repository
  quality + activity + portfolio composition), consistency (commit cadence,
  active days and calendar density/streaks), activity (commit volume, cadence,
  breadth), contribution (volume, density, streaks), community (followers,
  balance, reach), open-source (pull-request volume, merge rate, external and
  review engagement) and visibility (stars, followers, languages).
- **Overall aggregation** (issue #50) — `aggregate_dimension_scores` blends the
  scored dimensions by their configured weights into `OverallScore`; each
  `DimensionContribution` shows its score, weight and weighted contribution
  (which sum to the overall). Strengths and weaknesses are derived
  deterministically from the scores against the configured thresholds and
  capped lists, breaking ties on dimension id. `ProfileAnalysis` carries the
  result in its `overall` field.

## Recommendation layer (`recommendations/`)

Turns findings and low dimension scores into actionable, prioritized,
evidence-backed recommendations (issues #51–#53). Every recommendation is tied
to the finding or score that motivated it, so a report stays answerable:
*"why does this recommendation exist?"*.

- **Rule library** (`recommendations/rules.py`, issue #52) — `DEFAULT_RULES`
  maps every finding the analyzers emit to one of three classes: an actionable
  rule (producing a `Recommendation` with a template id, rationale, effort
  estimate, priority and metric references), a disclosure (`DISCLOSURE_PREFIXES`
  — missing/unavailable data surfaced as a red flag, never a recommendation) or
  a positive standout (`POSITIVE_PREFIXES` — surfaced as a strength). Rule
  patterns support exact, dotted-prefix and `*` single-segment wildcard
  matching; `extract_value` captures the matched segment for template
  interpolation, and `classify` raises on any unclassified finding so a missing
  rule surfaces immediately.
- **Engine** (`recommendations/engine.py`, issue #52) — `RecommendationEngine`
  maps findings to rules (one recommendation per actionable finding, carrying
  the finding's evidence as sources and severity) and emits low-score
  recommendations for dimensions at or below the weakness threshold, with
  severity/priority bands and a `dimension.low_score` template. The result is
  sorted into plan order by priority, then effort (quick wins first), then id.
  `backfill_finding_links` fills `Finding.recommendation_ids` so findings link
  back to the recommendations they produced.
- **Synthesis** (`recommendations/synthesis.py`, issue #53) — `synthesize`
  assembles the assessment narrative deterministically: strengths (dimension
  strengths plus positive standouts), weaknesses (dimension weaknesses plus
  quality issues), red flags (missing information, placeholder values and
  disclosures of unavailable data) and the prioritized plan. Ordering is fully
  deterministic (severity then id, priority then effort then id), so identical
  inputs produce identical syntheses.

## Report layer (`report/`)

Turns the assessment into shareable artifacts (issues #54–#57). The `Report`
DTO assembled here is the canonical serializable output; every renderer consumes
it directly, so all formats stay consistent and deterministic.

- **Assembly** (`report/assemble.py`, issue #55) — `run_analyses` executes every
  analyzer over a raw snapshot and wraps the results in a lazy `ProfileAnalyses`
  container, then `ReportAssembler.assemble` folds the analyses, dimensions,
  findings and recommendations into the final `Report` DTO. `Report` is
  `model_dump`-able and round-trips losslessly through JSON.
- **Markdown** (`report/markdown.py`, issue #56) — `render_markdown` emits a
  well-formatted document: per-analysis sections with curated property tables
  (byte units, percentages, `—` for missing values), sorted data tables for
  commits/PRs/issues/languages/domains, findings and recommendations ordered by
  severity and priority, and a flattened metrics appendix. The output is
  compared byte-for-byte against a checked-in golden file.
- **JSON** (`report/json.py`, issue #56) — `render_json`/`write_json` serialize
  the `Report` DTO losslessly, with `indent` and `ensure_ascii` options.
- **HTML** (`report/html.py`, issue #57) — `render_html` produces a fully static,
  self-contained dashboard: inline CSS dark theme, CSS-only bar charts for
  dimension scores, monthly contributions, language distribution and the
  most-starred ranking, collapsible findings/recommendations, and a full metrics
  table. No JavaScript and no external resources, so the file works offline and
  is byte-deterministic. Every dynamic value is HTML-escaped.

All renderers are pure functions over a `Report` and are covered by golden and
smoke tests under `tests/report/`.

## Derived data layer (`models/derived`)

- `MetricRecord` — id, label, value, **sources** (provenance), timestamp,
  confidence.
- `DimensionScore` + `ScoreBreakdown` — 0–100 score with weighted components,
  each component referencing the metric and raw inputs behind it.
- `OverallScore` + `DimensionContribution` — weighted overall score with
  per-dimension contributions and deterministic strengths/weaknesses.
- `Finding` — type, severity, evidence, recommendation references.
- `Recommendation` — priority, action, rationale, template id, severity, effort
  estimate, linked findings/metrics.
- `Synthesis` — strengths, weaknesses, red flags and the prioritized plan.
- `ProfileAnalysis` — snapshot container for one profile's analysis.
- `ProfileAnalyses` — lazy container holding every analyzer's output.
- `Report` — final serializable DTO assembled in the report layer.

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
- Coverage: **pytest-cov**, floor of **95%** enforced via `make coverage`
  (`[tool.coverage] fail_under` in `pyproject.toml`)
- One-command gate: **`make check`** (lint → format-check → typecheck → test)
- Pre-commit hooks run the same gates on every commit.

A clean checkout must pass `make check` before any work begins, and `make
coverage` confirms the unit-test coverage floor before merging.

## Testing & fixtures

Tests never hit the live GitHub API. The collection pipeline is exercised
through a versioned corpus of recorded responses (`tests/fixtures/corpus/`),
replayed via a strict `httpx` transport, so collectors through report rendering
run against deterministic data. Unit tests (including hypothesis-driven
property tests) target individual modules, and end-to-end tests replay every
corpus profile through the full collect → assemble → render pipeline. The
corpus is generated by a script and pinned by contract tests. See the [testing
& fixtures guide](testing.md) for the corpus format, the profile scenarios it
covers, the coverage gate, and how to regenerate it.
