"""Observability for collection runs (issue #65).

Structured, correlation-tagged logging plus timing and error metrics make a
failed collection run actionable: the JSON log stream shows exactly which
collections ran, how long they took, how many requests they used, and where
they failed, and the :class:`CollectionMetrics` snapshot adds aggregates that
survive report generation.

Exported API:

- :func:`configure_logging`, :func:`get_logger`, :func:`StructuredFormatter`,
  :func:`new_correlation_id`, :func:`get_correlation_id`,
  :func:`run_correlation` — from :mod:`~ghdtk.observability.logging`.
- :class:`CollectionMetrics`, :func:`run_timed` — from
  :mod:`~ghdtk.observability.metrics`.
"""

from ghdtk.observability.logging import (
    StructuredFormatter,
    configure_logging,
    get_correlation_id,
    get_logger,
    new_correlation_id,
    run_correlation,
)
from ghdtk.observability.metrics import CollectionMetrics, run_timed

__all__ = [
    "CollectionMetrics",
    "StructuredFormatter",
    "configure_logging",
    "get_correlation_id",
    "get_logger",
    "new_correlation_id",
    "run_correlation",
    "run_timed",
]
