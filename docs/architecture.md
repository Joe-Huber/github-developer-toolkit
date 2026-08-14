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
