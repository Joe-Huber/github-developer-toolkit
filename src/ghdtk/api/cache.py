"""API response caching (issue #21).

Repeated analyses of the same profile waste rate budget, so responses are
cached behind a pluggable backend. The cache is:

- **Keyed by a hash** of ``method:url`` — URLs are never stored as plaintext
  and the ``Authorization`` header is never persisted, so no secrets leak to
  disk or memory.
- **TTL-based** with stale-while-valid revalidation: an expired entry that
  carries an ``ETag`` is sent with ``If-None-Match``, and GitHub's ``304 Not
  Modified`` refreshes the entry instead of refetching the body.
- **Backend-swappable**: :class:`InMemoryCache` for tests and short runs,
  :class:`DiskCache` under a safe directory for real runs.
"""

from __future__ import annotations

import base64
import json
import os
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol

import httpx


def default_cache_directory() -> Path:
    """Return the platform-safe default cache directory (``~/.cache/ghdtk``)."""
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return root / "ghdtk"


def cache_key(method: str, url: str) -> str:
    """Return the stable hash key for a ``method`` + ``url`` pair."""
    return sha256(f"{method.upper()}:{url}".encode()).hexdigest()


@dataclass(frozen=True)
class CachedResponse:
    """A stored HTTP response with its TTL window."""

    key: str
    url: str
    status_code: int
    headers: dict[str, str]
    content: bytes
    stored_at: datetime
    expires_at: datetime
    etag: str | None = None

    def renewed(self, *, ttl_seconds: float, now: datetime | None = None) -> CachedResponse:
        """Return a copy with the expiry window extended from ``now``."""
        now = now or datetime.now(UTC)
        return CachedResponse(
            key=self.key,
            url=self.url,
            status_code=self.status_code,
            headers=self.headers,
            content=self.content,
            stored_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            etag=self.etag,
        )

    def redacted(self) -> CachedResponse:
        """Return a copy with the URL removed for safe on-disk storage."""
        return CachedResponse(
            key=self.key,
            url="<redacted>",
            status_code=self.status_code,
            headers=self.headers,
            content=self.content,
            stored_at=self.stored_at,
            expires_at=self.expires_at,
            etag=self.etag,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-serializable data."""
        return {
            "key": self.key,
            "url": self.url,
            "status_code": self.status_code,
            "headers": self.headers,
            "content": base64.b64encode(self.content).decode("ascii"),
            "stored_at": self.stored_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "etag": self.etag,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CachedResponse:
        """Reconstruct an entry from :meth:`to_dict` output."""
        return cls(
            key=data["key"],
            url=data["url"],
            status_code=data["status_code"],
            headers=dict(data["headers"]),
            content=base64.b64decode(data["content"]),
            stored_at=datetime.fromisoformat(data["stored_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            etag=data.get("etag"),
        )


class CacheBackend(Protocol):
    """Storage protocol implemented by both cache backends."""

    def get(self, key: str) -> CachedResponse | None:
        """Return the entry for ``key`` or ``None``."""
        ...

    def set(self, key: str, value: CachedResponse) -> None:
        """Store ``value`` under ``key``."""
        ...

    def delete(self, key: str) -> None:
        """Remove the entry for ``key``."""
        ...

    def clear(self) -> None:
        """Remove every entry."""
        ...


class InMemoryCache:
    """A dict-backed cache for tests and short-lived runs.

    Lock-guarded so concurrent collectors can share it (issue #63).
    """

    def __init__(self) -> None:
        self._entries: dict[str, CachedResponse] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> CachedResponse | None:
        with self._lock:
            return self._entries.get(key)

    def set(self, key: str, value: CachedResponse) -> None:
        with self._lock:
            self._entries[key] = value

    def delete(self, key: str) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


class DiskCache:
    """A directory-backed cache storing one JSON file per key.

    URLs are redacted before persistence; the ``Authorization`` header is never
    stored. Corrupt or unreadable files are treated as cache misses. Reads,
    writes and deletions are lock-guarded (and writes go through a temp-file
    rename) so parallel collectors never observe partial entries (issue #63).
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, key: str) -> Path:
        return self._directory / f"{key}.json"

    def get(self, key: str) -> CachedResponse | None:
        path = self._path(key)
        if not path.is_file():
            return None
        with self._lock:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return CachedResponse.from_dict(data)
            except (OSError, ValueError, KeyError):
                return None

    def set(self, key: str, value: CachedResponse) -> None:
        path = self._path(key)
        content = json.dumps(value.redacted().to_dict(), sort_keys=True)
        with self._lock:
            tmp = path.with_name(f".{path.name}.tmp")
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(path)

    def delete(self, key: str) -> None:
        with self._lock:
            self._path(key).unlink(missing_ok=True)

    def clear(self) -> None:
        with self._lock:
            for path in self._directory.glob("*.json"):
                path.unlink(missing_ok=True)


class ResponseCache:
    """TTL policy and stale-while-valid orchestration over a backend."""

    def __init__(self, backend: CacheBackend, *, ttl_seconds: float) -> None:
        self._backend = backend
        self._ttl = ttl_seconds

    @property
    def ttl_seconds(self) -> float:
        """The freshness window in seconds."""
        return self._ttl

    @property
    def backend(self) -> CacheBackend:
        """The underlying storage backend."""
        return self._backend

    def get(self, key: str) -> CachedResponse | None:
        """Return the entry for ``key``, fresh or stale."""
        return self._backend.get(key)

    @staticmethod
    def is_fresh(entry: CachedResponse, *, now: datetime | None = None) -> bool:
        """Whether the entry is still inside its TTL window."""
        now = now or datetime.now(UTC)
        return entry.expires_at > now

    def set(self, key: str, response: httpx.Response, url: str) -> None:
        """Store a successful response under ``key``."""
        now = datetime.now(UTC)
        entry = CachedResponse(
            key=key,
            url=url,
            status_code=response.status_code,
            headers=dict(response.headers),
            content=response.content,
            stored_at=now,
            expires_at=now + timedelta(seconds=self._ttl),
            etag=response.headers.get("ETag"),
        )
        self._backend.set(key, entry)

    def revalidate(self, key: str, entry: CachedResponse) -> CachedResponse:
        """Refresh the expiry of an ETag-confirmed entry and re-store it."""
        refreshed = entry.renewed(ttl_seconds=self._ttl)
        self._backend.set(key, refreshed)
        return refreshed

    def clear(self) -> None:
        """Evict every entry from the backend."""
        self._backend.clear()


def _entry_to_response(entry: CachedResponse, *, url: str) -> httpx.Response:
    """Rebuild an ``httpx.Response`` from a cached entry."""
    return httpx.Response(
        entry.status_code,
        content=entry.content,
        headers=entry.headers,
        request=httpx.Request("GET", url),
    )


__all__ = [
    "CacheBackend",
    "CachedResponse",
    "DiskCache",
    "InMemoryCache",
    "ResponseCache",
    "cache_key",
    "default_cache_directory",
]
