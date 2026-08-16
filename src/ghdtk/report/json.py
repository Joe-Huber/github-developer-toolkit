"""JSON report renderer (issue #56).

Serializes the :class:`Report` DTO to a JSON document that matches the DTO
schema losslessly (via ``model_dump_json``), with pretty/compact output and
path helpers. ``ensure_ascii=False`` keeps non-ASCII characters (em dashes,
user content) readable instead of escaping them.
"""

from __future__ import annotations

from pathlib import Path

from ghdtk.models.derived import Report


def render_json(report: Report, *, indent: int | None = 2, ensure_ascii: bool = False) -> str:
    """Serialize ``report`` to a JSON document.

    ``indent=None`` produces compact JSON; the default pretty-prints with two
    spaces of indentation.
    """
    return report.model_dump_json(indent=indent, ensure_ascii=ensure_ascii) + "\n"


def write_json(
    report: Report,
    path: str | Path,
    *,
    indent: int | None = 2,
    ensure_ascii: bool = False,
) -> Path:
    """Serialize ``report`` to JSON and write it to ``path``."""
    target = Path(path)
    target.write_text(
        render_json(report, indent=indent, ensure_ascii=ensure_ascii), encoding="utf-8"
    )
    return target


__all__ = ["render_json", "write_json"]
