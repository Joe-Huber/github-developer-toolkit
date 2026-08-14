"""Data models.

Strict separation between the raw data layer and the analysis layer:

- :mod:`ghdtk.models.raw` — immutable source-of-truth snapshots mirroring the
  GitHub API payloads. Never analyzed, never invented.
- :mod:`ghdtk.models.derived` — reproducible, explainable analysis output
  (metrics, scores, findings, recommendations, report DTO).

The data layer is agnostic to the analysis layer: raw models contain no
analysis logic, and derived models reference raw inputs only through
provenance.
"""
