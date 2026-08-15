"""Unit tests for rate-limit tracking and retry backoff (issue #18)."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from ghdtk.api.rate_limit import BackoffPolicy, RateLimitState, parse_retry_after


def _response(
    *, limit: str | None = None, remaining: str | None = None, reset: str | None = None
) -> httpx.Response:
    headers: dict[str, str] = {}
    if limit is not None:
        headers["X-RateLimit-Limit"] = limit
    if remaining is not None:
        headers["X-RateLimit-Remaining"] = remaining
    if reset is not None:
        headers["X-RateLimit-Reset"] = reset
    return httpx.Response(200, headers=headers)


def test_parse_retry_after_seconds() -> None:
    assert parse_retry_after("12") == 12.0
    assert parse_retry_after("1.5") == 1.5


def test_parse_retry_after_missing_or_invalid() -> None:
    assert parse_retry_after(None) is None
    assert parse_retry_after("soon") is None


def test_rate_limit_state_updates_from_headers() -> None:
    state = RateLimitState()
    state.update_from(_response(limit="5000", remaining="4999", reset="1800000000"))
    assert state.limit == 5000
    assert state.remaining == 4999
    assert state.reset_at == datetime.fromtimestamp(1_800_000_000, tz=UTC)


def test_rate_limit_state_ignores_bad_values() -> None:
    state = RateLimitState()
    state.update_from(_response(limit="nope", remaining="lots", reset="nope"))
    assert state.limit is None
    assert state.remaining is None
    assert state.reset_at is None


def test_rate_limit_state_exhausted() -> None:
    state = RateLimitState()
    assert not state.exhausted
    state.update_from(_response(remaining="0"))
    assert state.exhausted
    state.update_from(_response(remaining="5"))
    assert not state.exhausted


def test_wait_seconds_zero_when_not_exhausted() -> None:
    state = RateLimitState()
    state.update_from(_response(remaining="1", reset="1800000000"))
    assert state.wait_seconds() == 0.0


def test_wait_seconds_computed_until_reset() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    reset = int(now.timestamp()) + 60
    state = RateLimitState()
    state.update_from(_response(remaining="0", reset=str(reset)))
    wait = state.wait_seconds(now=now)
    assert 59.0 <= wait <= 61.0


def test_wait_seconds_never_negative() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    reset = int(now.timestamp()) - 60
    state = RateLimitState()
    state.update_from(_response(remaining="0", reset=str(reset)))
    assert state.wait_seconds(now=now) == 0.0


def test_rate_limit_state_to_dict() -> None:
    state = RateLimitState()
    state.update_from(_response(limit="5000", remaining="0", reset="1800000000"))
    data = state.to_dict()
    assert data["limit"] == 5000
    assert data["remaining"] == 0
    assert data["reset_at"] is not None


def test_rate_limit_state_to_dict_empty() -> None:
    assert RateLimitState().to_dict() == {
        "limit": None,
        "remaining": None,
        "reset_at": None,
    }


def test_backoff_delay_grows_and_is_capped() -> None:
    backoff = BackoffPolicy(base_delay=1.0, max_delay=10.0, random_fn=lambda low, high: 0.0)
    assert backoff.delay(1) == 1.0
    assert backoff.delay(2) == 2.0
    assert backoff.delay(4) == 8.0
    assert backoff.delay(10) == 10.0


def test_backoff_delay_applies_jitter() -> None:
    backoff = BackoffPolicy(base_delay=1.0, max_delay=10.0, random_fn=lambda low, high: 0.5)
    assert backoff.delay(1) == 1.5


def test_backoff_rejects_negative_delays() -> None:
    with pytest.raises(ValueError):
        BackoffPolicy(base_delay=-1.0)
    with pytest.raises(ValueError):
        BackoffPolicy(jitter=-0.1)


def test_backoff_sleep_uses_injected_function() -> None:
    slept: list[float] = []
    backoff = BackoffPolicy(sleep_fn=slept.append)
    backoff.sleep(2.5)
    assert slept == [2.5]
