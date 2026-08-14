"""Raw GitHub language statistics model.

The languages endpoint (``GET /repos/{owner}/{repo}/languages``) returns a bare
mapping of language name to bytes of code, e.g. ``{"Python": 38739}``. The
model wraps that mapping faithfully as a :class:`pydantic.RootModel`.
"""

from __future__ import annotations

from pydantic import ConfigDict, RootModel

from ghdtk.models.raw._base import BaseRawModel


class LanguageStats(RootModel[dict[str, int]]):
    """Bytes of code per language as returned by the languages endpoint."""

    model_config = ConfigDict(frozen=True)

    @property
    def total_bytes(self) -> int:
        """Total bytes of code across all languages."""
        return sum(self.root.values())

    @property
    def top_languages(self) -> list[tuple[str, int]]:
        """Languages sorted by bytes, largest first."""
        return sorted(self.root.items(), key=lambda item: item[1], reverse=True)


class LanguageStatsContainer(BaseRawModel):
    """Wrapper used when the languages payload appears nested in a snapshot."""

    languages: LanguageStats
