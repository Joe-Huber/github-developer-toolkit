"""Data collectors.

Fetch raw GitHub data through the API layer and deserialize it into immutable
:mod:`ghdtk.models.raw` snapshots. Collectors are the only place where raw
snapshots are created; analyzers never touch the network.

Implemented in a later issue; the module boundary is established here.
"""
