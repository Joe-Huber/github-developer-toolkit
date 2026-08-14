"""Raw GitHub README content model.

Mirrors the REST API response of ``GET /repos/{owner}/{repo}/readme``.
The file body is delivered base64-encoded in ``content``; the decoded text is
exposed through the read-only :attr:`Readme.decoded_content` property so the
raw snapshot itself stays a faithful copy of the payload.
"""

from __future__ import annotations

import base64

from ghdtk.models.raw._base import BaseRawModel


class Readme(BaseRawModel):
    """A repository README file as returned by the API."""

    type: str | None = None
    encoding: str | None = None
    size: int | None = None
    name: str | None = None
    path: str | None = None
    content: str | None = None
    sha: str | None = None
    url: str | None = None
    html_url: str | None = None
    git_url: str | None = None
    download_url: str | None = None

    @property
    def decoded_content(self) -> str | None:
        """Base64-decoded file content, or ``None`` when not available."""
        if self.content is None:
            return None
        if self.encoding is not None and self.encoding.lower() != "base64":
            return self.content
        return base64.b64decode(self.content).decode("utf-8")
