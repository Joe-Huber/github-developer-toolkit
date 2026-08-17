# Analysis Methodology & Scoring Explainability Guide

This document describes how the GitHub Developer Toolkit transforms raw GitHub
data into dimension scores, findings, and recommendations. It is the single
reference for every score formula, normalization method, heuristic, and known
limitation in the pipeline.

The goals of this document are:

1. Make every score reproducible from its inputs.
2. Disclose every limitation, bounded window, and heuristic caveat.
3. Provide a reference for the metric availability matrix and configurable
   thresholds.

---

## 1. Overview

### 1.1 Pipeline

The pipeline is a strict, unidirectional flow:

```
raw data  ->  metrics  ->  scores  ->  findings  ->  recommendations
```

Concretely:

1. **Collectors** fetch GitHub API payloads and deserialize them into immutable
   raw snapshots (`models/raw`). Raw data is never modified, analyzed, or
   annotated in place.
2. **Analyzers** consume raw snapshots and emit derived `MetricRecord`s and
   `Finding`s (`models/derived`). Each metric carries provenance pointing at
   the exact raw data that produced it.
3. **Scorers** combine metrics into 0-100 dimension scores with transparent
   weighted breakdowns (`scoring/`).
4. **The recommendation engine** turns findings and low scores into actionable,
   evidence-backed recommendations (`recommendations/`).

### 1.2 Strict separation of raw and derived data

Raw GitHub data is the single source of truth. The raw layer is frozen and
faithful: field names mirror the GitHub REST/GraphQL payloads, optional fields
default to `None` (never fabricated), and unknown fields are silently dropped.
Everything computed from raw data lives in the derived layer and references its
raw inputs.

### 1.3 Explainability and provenance

Every `MetricRecord` carries a typed `MetricAvailability` enum, a `value`, and
a `sources` tuple of `SourceReference` objects pointing at the raw entities
and fields behind it. Every `DimensionScore` carries a `ScoreBreakdown` list
showing each weighted component's normalized weight and contribution (which sum
exactly to the dimension score). Every `Finding` carries `evidence` referencing
the metrics and raw data that triggered it.

A report must always answer: *"why did I get this score?"*

---

## 2. Metric Availability

### 2.1 The `MetricAvailability` enum

Every metric emitted by the analyzers carries one of three availability levels:

- **`AVAILABLE`** -- reliable data from GitHub. The metric is a direct field or
  a deterministic derivation over direct fields. No bounded window or sampling
  caveat applies.
- **`PARTIAL`** -- bounded window or coverage. The metric is meaningful but
  reflects only the collected window (commit/PR/issue totals within the request
  budget), not the full lifetime. Partial metrics carry a coverage finding that
  states the observed bounds.
- **`UNAVAILABLE`** -- GitHub does not expose the data. The metric has
  `value=None` and a rationale explaining why. The pipeline never infers or
  fabricates a value for unavailable metrics.

### 2.2 Availability matrix

The centralized matrix (`analyzers/availability.py`) maps metric-id prefixes to
their documented availability. Longest prefix wins for resolution. This matrix
is the single source of truth; tests verify that every metric id the report
emits is covered.

| Family | Source | Reliability | Default |
|---|---|---|---|
| `presence` | User object (`GET /users/{username}`) | High | `AVAILABLE` |
| `readme` | Repository README (`GET /repos/{owner}/{repo}/readme`) | High | `AVAILABLE` |
| `portfolio.quality` | Repository metadata (`GET /users/{username}/repos`) | High | `AVAILABLE` |
| `portfolio.activity` | Repository metadata (`GET /users/{username}/repos`) | Medium | `PARTIAL` |
| `portfolio` | Repository list (`GET /users/{username}/repos`) | High | `AVAILABLE` |
| `portfolio.stars` | Repository list + stargazer timeline (preview header) | High | `AVAILABLE` |
| `star_growth` | Stargazer timeline (`GET /repos/{owner}/{repo}/stargazers`) | Medium | `PARTIAL` |
| `network` | User object + follower/following lists | High | `AVAILABLE` |
| `network.mutual_follows` | Computed from follower + following lists | Medium | `PARTIAL` |
| `network.followers.growth` | Not exposed by GitHub | Unavailable | `UNAVAILABLE` |
| `network.orgs.count` | Not exposed publicly | Unavailable | `UNAVAILABLE` |
| `commit_activity` | Per-repository commits (`GET /repos/{owner}/{repo}/commits?author=`) | Medium | `PARTIAL` |
| `contribution_calendar` | GraphQL `contributionsCollection` (`GET /graphql`) | Medium | `PARTIAL` |
| `pull_requests` | Search API + per-repository pulls (`GET /search/issues`, `/pulls`) | Medium | `PARTIAL` |
| `issues` | Search API + per-repository issues (`GET /search/issues`, `/issues`) | Medium | `PARTIAL` |
| `languages` | Per-repository languages (`GET /repos/{owner}/{repo}/languages`) | High | `AVAILABLE` |
| `tech` | Derived from per-repository language bytes | High | `AVAILABLE` |

### 2.3 Known caps

- **Commit history**: GitHub commit *search* (~1000 results per query) is not
  used. Commits are collected per repository (author-filtered listing) within
  the shared page cap and request budget, so results are a window, never
  complete lifetime history.
- **PR/issue search**: search results and pagination are bounded by page cap and
  budget. The coverage-window finding states the observed date span.
- **Follower/following lists**: bounded by the page cap per list. Reach is an
  estimate from the collected sample; partial samples fire a `partial_sample`
  finding.
- **Stargazer timeline**: only the most-starred owned (non-fork) repository is
  collected, bounded by the page cap.
- **Contribution calendar**: the GraphQL contribution calendar is a rolling
  ~365-day window. Private contributions may be hidden by the account.

---

## 3. Analysis Dimensions

The pipeline evaluates eight dimensions. Each dimension is scored independently
by a dedicated scorer that documents its formula, inputs, and edge-case
behavior.

### 3.1 Profile Presence (`presence`)

**Inputs**: `assess_profile_presence` producing `ProfilePresence`, plus
`assess_readme_quality` producing `ReadmeAssessment`.

**Metrics**: per-field presence status (present/missing/placeholder), account
age, placeholder detection via heuristic pattern matching, README word count,
headings, code blocks, links, images, badges, username mentions, and
boilerplate detection.

**Scoring formula** (blended, 0-100):

| Component | Weight | Formula |
|---|---|---|
| Profile field completeness | 1.0 | `normalize_ratio(present_fields / total_fields)` |
| Profile README quality | 1.0 | See below |

When no README was assessed, the README component is dropped and the remaining
weight is re-normalized.

README quality sub-formula:

```
readme_quality = 0.40 * word_component + 0.35 * structure_component + 0.25 * personalization
```

- **Word component**: `normalize_ratio(min(word_count / 100, 1.0))`
- **Structure component**: `normalize_ratio(sum(headings_present, code_blocks_present, links_present, images_or_badges_present) / 4)`
- **Personalization**: 100.0 if username mentions > 0, else 0.0; capped at 50.0
  when boilerplate wording is detected.

**Limitations**: placeholder detection is deliberately conservative (see
Section 5). A README that is missing, empty, or failed to fetch scores zero.
### 3.2 Code Quality (`code_quality`)

**Inputs**: `assess_repository_quality` producing `RepositoryQuality`,
`assess_repository_activity` producing `RepositoryActivity`, and
`assess_portfolio_composition` producing `PortfolioComposition`.

**Metrics**: description/README/license/homepage coverage ratios, average topics
per repository, active/dormant repository counts, median staleness, standout
count, and total portfolio stars.

**Scoring formula** (blended, 0-100):

| Component | Weight | Formula |
|---|---|---|
| Repository quality | 1.0 | See sub-formula below |
| Repository activity | 0.5 | `0.50 * active_share + 0.50 * staleness` |
| Portfolio composition | 0.25 | `0.60 * standout_component + 0.40 * stars_component` |

When repository activity or portfolio composition analyses were not run, their
components are dropped and the remaining weight is re-normalized.

Repository quality sub-formula:

```
quality = 0.30 * normalize_ratio(description_coverage)
        + 0.30 * normalize_ratio(readme_coverage)
        + 0.15 * normalize_ratio(license_coverage)
        + 0.10 * normalize_ratio(homepage_coverage)
        + 0.15 * normalize_linear(topics_average, 0, 5)
```

Activity sub-formula:

- **Active share**: `normalize_ratio(active_repos / total_repos)`
- **Staleness**: `normalize_linear(median_staleness_days, 0, 90, high_is_good=False)`

Portfolio composition sub-formula:

- **Standout component**: `normalize_linear(standout_count, 0, 3)`
- **Stars component**: `normalize_log(total_stars, 1.0, star_volume_target)`

**Limitations**: forked and archived repositories are excluded from quality
signals (forks counted but excluded from recency; archived get an informational
finding). Activity is bounded by the page cap per repository.

### 3.3 Consistency (`consistency`)

**Inputs**: `assess_commit_activity` producing `CommitActivity`, plus
`assess_contribution_calendar` producing `ContributionCalendarAnalysis`.

**Metrics**: commit cadence (commits/month), active days, median and longest
inter-commit gaps, contribution density, current and longest streaks, longest
inactive run.

**Scoring formula** (blended, 0-100):

| Component | Weight | Formula |
|---|---|---|
| Commit regularity | 0.7 | See sub-formula below |
| Calendar regularity | 0.3 | See sub-formula below |

When the contribution calendar was not run, the calendar component is dropped
and the remaining weight is re-normalized.

Commit regularity sub-formula:

```
commit_regularity = 0.50 * cadence_component
                  + 0.30 * gap_component
                  + 0.20 * active_share
```

- **Cadence**: `normalize_linear(cadence_per_month, 0, cadence_target)` where
  `cadence_target` defaults to 4.0 commits/month.
- **Gap**: `normalize_linear(median_gap_days, gap_good_days, gap_bad_days, high_is_good=False)`
  where `gap_good_days` = 14 and `gap_bad_days` = 60. When there is no median
  gap (zero commits), this component scores 100.
- **Active share**: `normalize_ratio(active_days / span_days)` when
  `span_days > 0`, otherwise `normalize_linear(active_days, 0, 90)`.

Calendar regularity sub-formula:

```
calendar_regularity = 0.50 * density_component
                    + 0.25 * streak_component
                    + 0.25 * gap_component
```

- **Density**: `normalize_ratio(density)`
- **Streak**: `normalize_linear(longest_streak, 0, 30)`
- **Gap**: `normalize_linear(longest_gap_days, gap_good_days, gap_bad_days, high_is_good=False)`; 100
  when no gap exists.

**Limitations**: commit history is a window over the collected period, not
lifetime. The coverage window finding states the observed date span. GitHub
search caps at ~1000 results, but search is not used for commits; per-repo
listing is bounded by page cap and budget.

### 3.4 Activity (`activity`)

**Inputs**: `assess_commit_activity` producing `CommitActivity`.

**Metrics**: total commits, cadence per month, active day count.

**Scoring formula** (blended, 0-100):

| Component | Weight | Formula |
|---|---|---|
| Commit volume | 0.4 | `normalize_log(total_commits, 1.0, activity_volume_target)` |
| Commit cadence | 0.3 | `normalize_linear(cadence_per_month, 0, cadence_target)` |
| Active-day breadth | 0.3 | `normalize_linear(active_days, 0, 90)` |

Where `activity_volume_target` defaults to 1000 and `cadence_target` defaults
to 4.0.

**Limitations**: bounded by the page cap per repository. A coverage window
with no commits scores zero on every component.

### 3.5 Contribution (`contribution`)

**Inputs**: `assess_contribution_calendar` producing
`ContributionCalendarAnalysis`.

**Metrics**: total contributions, density (share of active days), longest
streak, longest gap.

**Scoring formula** (blended, 0-100):

| Component | Weight | Formula |
|---|---|---|
| Contribution volume | 0.4 | `normalize_log(total_contributions, 1.0, contribution_volume_target)` |
| Contribution density | 0.35 | `normalize_ratio(density)` |
| Streaks and gaps | 0.25 | `0.60 * streak_component + 0.40 * gap_component` |

Where:

- `contribution_volume_target` defaults to 5000.
- **Streak**: `normalize_linear(longest_streak, 0, 30)`.
- **Gap**: `normalize_linear(longest_gap_days, gap_good_days, gap_bad_days, high_is_good=False)`;
  scores 100 when no gap exists.
- The streak blend is 0.0 when there is no contribution data.

**Limitations**: the contribution calendar is a rolling ~365-day window, not
lifetime. Private contributions may be hidden by the account; hidden
contributions are disclosed via `restrictedContributionsCount`, never assumed.

### 3.6 Community (`engagement`)

**Inputs**: `assess_follower_network` producing `FollowerNetwork`.

**Metrics**: follower count, follower/following ratio, reach estimate.

**Scoring formula** (blended, 0-100):

| Component | Weight | Formula |
|---|---|---|
| Follower audience | 0.4 | `normalize_log(followers, 1.0, follower_volume_target)` |
| Follower balance | 0.3 | `clamp(ratio, 0.0, 1.0) * 100.0` |
| Network reach | 0.3 | `normalize_log(reach, 1.0, follower_volume_target * 5)` |

Where `follower_volume_target` defaults to 1000. The ratio is taken from the
network analysis; when absent, it is derived from raw counts
(`followers / following`, or 1.0 when followers > 0 and following is absent,
or 0.0 when followers is 0).

**Limitations**:

- Follower growth history is `UNAVAILABLE` -- GitHub does not expose the data.
- Organization membership is `UNAVAILABLE` -- the public user object exposes no
  org count field; extra scopes are required.
- Reach is an estimate from the collected follower sample. Partial samples fire
  a `partial_sample` finding. Mutual follows are computed from the collected
  follower/following samples and are an estimate unless both lists fully cover
  their reported counts.

### 3.7 Open Source (`open_source`)

**Inputs**: `assess_pull_request_collaboration` producing `PullRequestAnalysis`
and `assess_issue_participation` producing `IssueParticipationAnalysis`.

**Metrics**: total pull requests, merge rate, external-repository share,
review-comment share, issue close rate, comment engagement.

**Scoring formula** (blended, 0-100):

| Component | Weight | Formula |
|---|---|---|
| Pull-request volume | 0.3 | `normalize_log(total_prs, 1.0, pr_volume_target)` |
| Pull-request merge rate | 0.3 | `normalize_ratio(merge_rate)` |
| External engagement | 0.2 | `normalize_ratio(external_share)` |
| Review collaboration | 0.2 | `normalize_ratio(reviewed_share)` |

Where `pr_volume_target` defaults to 300.

**Limitations**:

- Search API window: results reflect the collected window, not lifetime.
- External detection relies on the snapshot's repository list. A repo is
  "external" when it is not one of the profile's own repositories; items that
  name no repository are disclosed, never guessed.
- Trends require sufficient months and issues (configurable minimums) before a
  rising/slowing direction is drawn.

### 3.8 Visibility (`visibility`)

**Inputs**: `assess_star_distribution` producing `StarsAnalysis`,
`assess_follower_network` producing `FollowerNetwork`, and
`assess_language_distribution` producing `LanguageDistributionAnalysis`.

**Metrics**: total stars, star distribution percentiles, top-starred ranking,
follower count, distinct languages, repos with byte statistics.

**Scoring formula** (blended, 0-100):

| Component | Weight | Formula |
|---|---|---|
| Portfolio stars | 0.6 | `normalize_log(total_stars, 1.0, star_volume_target)` |
| Language diversity | 0.4 | `0.60 * distinct_component + 0.40 * coverage_component` |

When the language analysis was not run, the language component is dropped and
the star component takes full weight (1.0).

Where `star_volume_target` defaults to 5000. Language diversity sub-formula:

- **Distinct**: `normalize_linear(distinct_languages, 0, 8)`
- **Coverage**: `normalize_ratio(repos_with_byte_stats / total_repos)`

**Limitations**: fork star reporting is separate from owned-repository stars.
All aggregates and the ranking are computed over owned repositories per the
documented fork policy.

---

## 4. Scoring Framework

### 4.1 Dimension Weights

The overall profile score is a weighted average of all scored dimensions. The
default weights are:

| Dimension | Weight |
|---|---|
| Profile presence | 1.0 |
| Code quality | 1.5 |
| Consistency | 1.0 |
| Activity | 1.5 |
| Contribution | 1.5 |
| Community | 1.0 |
| Open source | 1.0 |
| Visibility | 1.0 |

Activity, contribution, and code quality carry 1.5x weight because they are
the strongest signals of an active, healthy developer profile. Weights are
configurable via `ScoringConfig`; a weight of zero excludes a dimension from
the overall aggregation while keeping its individual score available.

### 4.2 Normalization helpers

All scorers output 0-100 scores. The normalization building blocks are:

**`clamp(value, low=0.0, high=100.0)`** -- Clamps a value into `[low, high]`.
All normalization helpers use this to prevent out-of-range scores.

**`normalize_ratio(ratio, scale=100.0)`** -- Maps a `[0, 1]` ratio onto
`[0, scale]`. Input is clamped to `[0, 1]` before scaling. Used for share-based
components (merge rate, field coverage, density).

**`normalize_linear(value, low, high, high_is_good=True)`** -- Linearly maps
`value` in `[low, high]` to `[0, 100]`. Out-of-range values are clamped. When
`high_is_good=False` the mapping is inverted so `low` is the full-credit
anchor. A degenerate `low == high` range grants full credit exactly at the
single anchor.

**`normalize_log(value, low, high, high_is_good=True, base=10.0)`** -- Log
scaling maps `value` in `(low, high]` to `[0, 100]` logarithmically. Log
scaling compresses large ranges so moving from 0 to 1000 counts like moving
from 1000 to 10000. Requires `0 < low < high`; values at or below `low` score
zero, values at or above `high` score full credit. Used for volume components
(commit count, star count, follower count, PR count, contribution count).

**`blend(components)`** -- Weighted average with transparent breakdown. The
blended score is the weighted average of component values. Each returned
`ScoreBreakdown` carries its normalized weight (the share of total weight) and
its contribution (`value * normalized_weight`), so the contributions sum
exactly to the blended score. With no positive weight the score is zero and the
breakdown is empty.

### 4.3 Overall score

The overall profile score is computed by `aggregate_dimension_scores`:

```
overall = sum(dimension_score * dimension_weight) / sum(dimension_weights)
```

Each `DimensionContribution` shows its score, weight, and weighted contribution
(which sum to the overall).

**Strengths** are dimensions at or above `strength_threshold` (default 70),
ranked best first, capped at 3.

**Weaknesses** are dimensions at or below `weakness_threshold` (default 40),
ranked worst first, capped at 3.

Ties break on the dimension id so the output is deterministic.

---

## 5. Heuristics and Their Limits

### 5.1 Placeholder detection

Source: `analyzers/heuristics.py`.

The placeholder detector uses conservative regular expressions and phrase
lists. It matches only obvious scaffolding and generic template wording.

**Placeholder patterns** (matched case-insensitively):

- `lorem ipsum`
- `example.com`
- `yourdomain`
- `example-domain`
- `(your|my|insert) (company|domain|website|site|project|handle|username|name|bio)`
- `change me`
- `coming soon`
- `todo`
- `placeholder`
- `tbd`
- `@your(username|handle|twitter)`
- `<your...>` / `<insert...>` HTML tags

**Boilerplate phrases** (lowercase substring match):

- "this is a readme" / "this is a profile readme" / "this is my readme"
- "here is my readme"
- "welcome to my github profile" / "you found my github profile"
- "feel free to use this template" / "made from a template" / "built with a template" / "based on a template"

**False-positive caveat**: a company genuinely named "Example", a bio that
quotes "lorem ipsum", or a README that intentionally uses template wording can
all match. Every match is surfaced as a finding with the matched text as
evidence, never as ground truth. The matching text is always included so an
analyst can judge the match themselves.

### 5.2 External repository detection

A repository is "external" when it is not one of the profile's own repositories
in the snapshot. Items that name no repository are disclosed with an
informational finding, never guessed. The detection relies entirely on the
collected repository list; if the list is incomplete (budget-capped), external
detection may misclassify some repositories.

### 5.3 Reach estimates

Follower/following coverage confidence equals the observed coverage. When the
follower list was not fully collected (bounded by page cap), reach is reported
as an estimate from the sample. A `partial_sample` finding fires when coverage
is less than 100%, and the finding carries the observed coverage percentage.

### 5.4 Streak calculations

Streaks are run-lengths over the returned calendar window, not lifetime. Notable
streaks fire at or above `streak_notable_days`. Long inactive runs fire at or
above `contribution_gap_days`. The calendar window is approximately 365 days
from the GraphQL `contributionsCollection`.

---

## 6. Key Configurable Thresholds

All thresholds are configurable via `ghdtk.toml`, environment variables
(`GHDTK_*`), or the settings object. Defaults are validated with Pydantic.

| Setting | Default | Used by |
|---|---|---|
| `analysis_staleness_days` | 90 | Repository activity staleness detection |
| `analysis_minimum_stars` | 10 | Standout detection (minimum stars for a standout repo) |
| `analysis_minimum_repositories` | 3 | Portfolio minimum size |
| `analysis_readme_min_chars` | 100 | README length assessment |
| `analysis_minimum_commits` | 5 | Commit activity minimum |
| `scoring_cadence_target` | 4.0 | Commit cadence target (commits per month) |
| `scoring_gap_good_days` | 14 | Active gap threshold (median/longest gap at or below = full credit) |
| `scoring_gap_bad_days` | 60 | Long-gap threshold (gap at or beyond = zero credit) |
| `scoring_strength_threshold` | 70.0 | Dimension score at or above which it counts as a strength |
| `scoring_weakness_threshold` | 40.0 | Dimension score at or below which it counts as a weakness |

Additional internal constants (not directly exposed in settings):

| Constant | Value | Used by |
|---|---|---|
| `activity_volume_target` | 1000 | Activity scorer: log-scaled commit volume |
| `contribution_volume_target` | 5000 | Contribution scorer: log-scaled contribution volume |
| `star_volume_target` | 5000 | Visibility scorer: log-scaled star volume |
| `follower_volume_target` | 1000 | Community scorer: log-scaled follower volume |
| `pr_volume_target` | 300 | Open-source scorer: log-scaled PR volume |
| Streak target | 30 days | Consistency and contribution scorers: linear streak credit |
| Active day target | 90 days | Activity and consistency scorers: linear active-day breadth |
| Topics target | 5 topics | Code quality scorer: linear average topics per repo |
| Standout target | 3 repos | Code quality scorer: linear standout count |
| Languages target | 8 | Visibility scorer: linear distinct-language count |

---

## 7. Data Collection Budget

### 7.1 Request budget

A single profile run is bounded by a hard cap on API requests:

| Setting | Default | Description |
|---|---|---|
| `collection_max_requests` | 500 | Maximum HTTP requests per profile run |
| `collection_max_workers` | 1 | Parallel workers (1 = sequential, up to 32) |

### 7.2 Budget tracking

`CollectionBudget` tracks requests against the hard cap, thread-safely. It
supports reservation-based accounting (`reserve`/`settle`) so the orchestrator
can dispatch parallel groups without letting combined bursts exceed the cap:

1. **Reserve**: before dispatching a collection, the orchestrator atomically
   reserves an estimated number of requests. If the reservation would exceed
   the cap, the dispatch is refused.
2. **Settle**: after the collection completes, the reservation is reconciled
   against actual requests used. Unused reservation capacity is released; any
   overrun is charged.

### 7.3 Budget-exhausted behavior

Paginated collections never exceed the remaining budget. Collections that no
longer fit are skipped with an explicit `budget_exhausted` status in the
`ProfileSnapshot`'s `CollectionRecord`. The run continues; partial data is
recorded and the snapshot is marked `is_partial`.

### 7.4 Collection priority

The orchestrator schedules collectors by dependency and priority:

1. **Core profile** (highest priority): user object, repositories, contribution
   calendar, followers, following.
2. **Cross-repository search**: PR and issue search collections.
3. **Per-repository metadata**: languages, readme, commits, pull requests,
   issues -- sorted by star count.
4. **Stargazer timeline**: only for the most-starred owned (non-fork)
   repository.

Collections that depend on earlier results (e.g., per-repo metadata needs the
repository list) wait for their dependencies. The per-repository metadata phase
runs sequentially by default (`max_workers=1`); a higher value dispatches
groups in a thread pool while respecting the budget.
