"""Report generation.

Serializes a completed analysis into the final report DTO for display or
export.

Implemented layers:

- :mod:`~ghdtk.report.assemble` — the :class:`ReportAssembler` pipeline that
  turns a raw snapshot into the complete report DTO (issue #55).
- :mod:`~ghdtk.report.markdown` — complete, well-formatted Markdown rendering
  of the report (issue #56).
- :mod:`~ghdtk.report.json` — lossless JSON serialization matching the DTO
  schema, with pretty/compact output (issue #56).
"""

from __future__ import annotations

from ghdtk.report.assemble import ReportAssembler, run_analyses
from ghdtk.report.json import render_json, write_json
from ghdtk.report.markdown import render_markdown, write_markdown

__all__ = [
    "ReportAssembler",
    "render_json",
    "render_markdown",
    "run_analyses",
    "write_json",
    "write_markdown",
]
