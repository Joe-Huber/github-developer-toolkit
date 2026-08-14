"""GitHub API client layer.

Responsible for talking to the GitHub REST/GraphQL APIs, authentication, rate
limit handling, retries, and returning raw payloads for the collectors.
Collectors turn these payloads into :mod:`ghdtk.models.raw` snapshots.

Implemented in a later issue; the module boundary is established here.
"""
