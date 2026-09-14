# Dashboard

The interactive web dashboard visualizes GitHub profile analysis results using a **FastAPI backend** and **React frontend**.

## Quick start

```bash
# Install with dashboard dependencies
pip install "ghdtk[dashboard]"
# or from source:
uv pip install -e ".[dashboard]"

# Run the dashboard (opens browser automatically)
ghdtk dashboard octocat

# Custom port
ghdtk dashboard octocat --port 3000
```

## Architecture

```
┌──────────────┐     GET /api/report/{user}     ┌──────────────┐
│   React UI   │ ──────────────────────────────> │   FastAPI    │
│  (Vite SPA)  │ <────── JSON Report ─────────── │  (Python)    │
│  :5173 dev   │                                 │  :8000       │
└──────────────┘                                 └──────┬───────┘
                                                        │
                              collect_profile() + assemble()
                                                        │
                                                        v
                                                 ┌──────────────┐
                                                 │  GitHub API  │
                                                 └──────────────┘
```

**Development:** Vite dev server on `:5173`, proxies `/api` to FastAPI on `:8000`.
**Production:** FastAPI serves the built React SPA from `dashboard-ui/dist/`.

## Development setup

```bash
# Terminal 1 — Python backend
ghdtk dashboard --no-open

# Terminal 2 — React frontend (hot reload)
cd dashboard-ui
npm install
npm run dev
```

Vite automatically proxies API requests to the backend.

## Building for production

```bash
# Build the React frontend
cd dashboard-ui
npm run build

# FastAPI serves it automatically at /
ghdtk dashboard octocat
```

## Running tests

```bash
# Python backend tests
uv run pytest tests/dashboard/ -v

# React frontend tests
cd dashboard-ui
npm test
```

## Profile page

Searching a username opens the dashboard on the **Profile** tab, which renders
the identity header and top-statistics blocks. It is also reachable from the
sidebar and via deep links such as `?user=octocat&tab=profile`.

- **Identity header** — name, avatar (initials fallback), handle, bio,
  "Open to opportunities" badge, and location / company / website / email /
  Twitter detail rows sourced from the GitHub user record (`profile.identity`).
- **Top statistics** — headline numbers: public repositories, total stars,
  forks, followers, following, and public gists, plus collected commit /
  pull-request / issue / contribution counts (`profile.top_stats.metrics`).
- **Top repositories** — up to five most-starred user repositories (forks
  excluded), each linking out to GitHub.
- **Languages** — byte-derived share of the profile's repositories.

**Availability semantics:** every metric carries an
`available | partial | unavailable` badge. Counts derived from a partial
snapshot (e.g. commits, PRs, issues, contributions) are marked `partial`, and
the whole block is `partially available` when the underlying snapshot is
partial. Blocks degrade gracefully: a missing `identity` or `top_stats` renders
an "unavailable" state rather than failing.

**Data boundary:** these blocks are derived entirely from the collected
snapshot — the dashboard makes no additional GitHub API calls.

## API endpoints

| Method | Path                  | Description                          |
|--------|-----------------------|--------------------------------------|
| GET    | `/api/health`         | Health check — returns `{"status": "ok"}` |
| GET    | `/api/report/{user}`  | Runs full analysis pipeline, returns `ReportResponse` |

## Configuration

The dashboard inherits the same configuration as the CLI:

- `GHDTK_GITHUB_TOKEN` — GitHub token (or `.env` / keyring)
- `GHDTK_COLLECTION_MAX_REQUESTS` — API budget (default: 60)
- `GHDTK_COLLECTION_MAX_WORKERS` — Parallel workers (default: 1)

Set these in a `.env` file in the project root or export as environment variables.
