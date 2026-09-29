# README images

Screenshots and terminal captures embedded in the top-level [README](../../README.md).
All of them show **[@Joe-Huber](https://github.com/Joe-Huber)** — real profile,
real numbers.

## How they were produced

No valid token was available when these were captured, so the collection
pipeline was driven through a **recorded session** instead of the live API:

1. All 91 REST responses for `collect_profile("Joe-Huber")` were fetched from
   the public `api.github.com` endpoints (user, repos, followers, following,
   PR/issue search, per-repo languages/readme/commits/pulls/issues, profile
   README) and stored as a replay session.
2. The contribution calendar came from the public
   `github.com/users/Joe-Huber/contributions` page (367 days, 2,693 total —
   matching the profile header). It stands in for the `POST /graphql` query,
   which requires authentication.
3. The built SPA was served with `collect_profile` patched to the replay
   client, so `GET /api/report/Joe-Huber` returns the recorded data; the CLI
   ran the same way. Captures are light-theme, 1800px wide, 256-colour.

## Known artifacts (vs. a live run with your own token)

- The terminal capture shows `0.1s` and exit code 4: replay answers instantly,
  and the stargazer-timeline collection fails without a token (GitHub now
  requires authentication for `/stargazers`). With a token it is `83/83`,
  exit 0, and takes tens of seconds.
- Star-growth velocity is therefore absent from the report; everything else is
  byte-identical to a live run.

## Refreshing them

With a valid `GHDTK_GITHUB_TOKEN`:

| File | How to recapture |
| --- | --- |
| `dashboard-overview.png` | `ghdtk dashboard Joe-Huber` → tab `overview` |
| `dashboard-profile.png` | tab `profile` |
| `dashboard-dimension.png` | tab `code_quality` (or any dimension) |
| `cli-analyze.png` | real terminal running `ghdtk analyze Joe-Huber` |
| `report-html.png` | `ghdtk analyze Joe-Huber -f html`, opened in a browser |

Keep the light theme and cap the width at 1800px.
