# Testing & Fixtures

This document describes the testing strategy and the recorded-response fixture
corpus used to exercise the collection pipeline without touching the live API.
It is the fixture guide referenced by issue #59 and the base for the unit (#60)
and integration/end-to-end (#61) suites. The quality gates described here back
the epic [#58](https://github.com/Joe-Huber/github-developer-toolkit/issues/58).

## Test strategy

Tests never call the live GitHub API. The pipeline is driven through a real
`GitHubClient` with an injected `httpx` transport that serves recorded
responses, so every layer below the transport — collectors, analyzers, scoring,
recommendations and report rendering — runs against realistic, deterministic
data.

Three layers build on each other:

1. **Fixture corpus** (`tests/fixtures/corpus/`) — versioned, generated
   recordings of the requests a full collection makes for each profile and the
   responses it receives. This document is their guide.
2. **Unit tests** (`tests/api`, `tests/collectors`, `tests/analyzers`,
   `tests/scoring`, `tests/report`, `tests/models`, `tests/observability`, ...)
   — targeted per-module tests, including raw JSON fixtures under
   `tests/fixtures/raw/`. Normalization/property tests
   (`tests/api/test_normalizers_property.py`) use **hypothesis** to generate
   inputs and assert invariants (shares sum to one, counts are bounded,
   summaries agree with their inputs). Observability tests
   (`tests/observability/`) cover structured formatter JSON shape, correlation
   id scoping and thread propagation, configure_logging idempotency, and
   thread-safe CollectionMetrics timing/counters.
3. **Integration & end-to-end tests** (`tests/fixtures/test_end_to_end.py`) —
   replay every full profile session end to end (`collect_profile` → profile
   README → `ReportAssembler` → all renderers), asserting the artifacts are
   complete, deterministic and regression-free (issue #61).

## Coverage gate

The repository enforces a unit-test coverage floor of **95%** on the `ghdtk`
package, configured in `[tool.coverage]` in `pyproject.toml`. The gate runs as:

```sh
make coverage        # pytest --cov=ghdtk; threshold read from pyproject
```

`make coverage` reports per-module gaps with missing line numbers, so an
uncovered branch in a new module is visible immediately. The `make check` gate
is the fast loop (lint → format-check → typecheck → test) and does not run
coverage; run `make coverage` before merging to confirm the floor still holds.
Pre-commit hooks run the same checks on every commit, with mypy given the same
dependency set the project uses (including `hypothesis` for the property
tests).

## Corpus layout

```
tests/fixtures/corpus/
├── MANIFEST.json                      # version + index of every session
├── active-developer/session.json      # jane-doe
├── minimal-profile/session.json       # ghost-user
├── newcomer/session.json              # new-dev
├── popular-maintainer/session.json    # ada-dev
├── archived-heavy/session.json        # historian
├── hidden-activity/session.json       # private-dev
└── errors/
    ├── user-not-found/session.json    # 404 on /users/{username}
    ├── rate-limit/session.json        # 403 + X-RateLimit-* headers
    └── malformed/session.json         # non-JSON body
```

Every directory under the corpus holds one `session.json`. The `MANIFEST.json`
records the corpus version and, for each profile, its id, username and request
count.

## Session format

A session is a JSON document with a version, profile metadata and the ordered
set of requests the collection pipeline is expected to make:

```json
{
  "version": 1,
  "profile": {
    "id": "active-developer",
    "username": "jane-doe",
    "description": "...",
    "now": "2026-01-01T12:00:00Z"
  },
  "requests": [
    {
      "method": "GET",
      "path": "/users/jane-doe/repos",
      "params": {"per_page": "100", "page": "1"},
      "response": {
        "status": 200,
        "headers": {"Link": "<...>; rel=\"next\""},
        "body": [...]
      }
    }
  ]
}
```

Response bodies may instead be stored as a base64 `"content"` string when the
payload is binary (for example the profile README). `headers` carry whatever
matters to the client: pagination `Link` headers, `X-RateLimit-*` headers and so
on.

## Profiles & scenarios

| Profile | Id | Exercises |
| --- | --- | --- |
| active-developer | `active-developer` | healthy profile, 3 repos, merged PRs, issues, stargazers, README present |
| minimal-profile | `minimal-profile` | brand-new user, no repositories, no followers, no README |
| newcomer | `newcomer` | one young repository, no README repo |
| popular-maintainer | `popular-maintainer` | several repos, most-starred non-fork, README present |
| archived-heavy | `archived-heavy` | multiple archived repositories |
| hidden-activity | `hidden-activity` | no commits in the searchable window, boilerplate README + placeholder descriptions |
| error: user-not-found | `errors/user-not-found` | 404 → `UserNotFoundError` |
| error: rate-limit | `errors/rate-limit` | 403 with rate-limit headers → `RateLimitError` |
| error: malformed | `errors/malformed` | non-JSON body → `MalformedResponseError` |

## Regeneration

The corpus is generated, not hand-edited. Regenerating is a deliberate step
that rewrites every session and the manifest:

```sh
python tests/fixtures/generate_corpus.py
```

The generator builds payloads from small base builders so the corpus stays
coherent: a repository referenced by a commit, pull request, issue or stargazer
entry always exists in that profile's repository list, and search results only
reference repositories the profile actually has. After regenerating, run
`make check` — `tests/fixtures/test_corpus.py` pins the format, the manifest,
strict-replay invariants and end-to-end coherence of every session.

## Replaying sessions in tests

`tests/fixtures/replay.py` turns a session into a working client:

```python
from replay import client_from_session, list_profiles, load_session

session = load_session("active-developer")
client = client_from_session(session)

snapshot = collect_profile(client, session["profile"]["username"], now=...)
```

`ReplayTransport` matches requests on method, path and sorted query parameters
and serves the recorded response. In **strict mode** (the default) any request
that is not in the session raises `UnrecordedRequestError`, so tests fail loudly
if the pipeline starts making requests the corpus was not designed for — the
corpus is a contract, not a loose stub. Lenient mode (`strict=False`) answers
unknown requests with a 404 for ad-hoc exploration.

`list_profiles()` returns the ids of the full (non-error) profiles so test
suites can parametrize over the corpus automatically.

## Rules

- **Never touch the live API.** All requests go through `ReplayTransport`
  (strict). A corpus test asserts `client.requests_made == len(session["requests"])`.
- **Versioned.** The corpus version is pinned in `CORPUS_VERSION`; loading or
  replaying a session of another version raises `SessionVersionError`.
- **Deterministic.** The generator is seeded by structure, not randomness, and
  a full collection replay produces an identical
  `ProfileSnapshot.model_dump(mode="json")` across runs.
- **Coherent.** Referenced repositories, contributors and search results always
  resolve within the session.
- **Documented.** Any new scenario or endpoint added to the corpus must update
  this guide, the generator, and the corpus contract tests in one commit.
