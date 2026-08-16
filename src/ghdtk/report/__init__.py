"""Report generation.

Serializes a completed analysis into the final report DTO for display or
export.

Implemented layers:

- :mod:`~ghdtk.report.assemble` — the :class:`ReportAssembler` pipeline that
  turns a raw snapshot into the complete report DTO (issue #55).
"""

from __future__ import annotations

from ghdtk.report.assemble import ReportAssembler, run_analyses

__all__ = [
    "ReportAssembler",
    "run_analyses",
]
