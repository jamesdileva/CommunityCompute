"""CreatorLab protocol package. Full message schemas land in Phase 2 (Sprint 1-2).

Planned messages (implementation-guide §4): WorkerRegistration, Heartbeat, WorkUnit, WorkResult.
Every message envelope carries ``protocol_version`` so the protocol can evolve.
"""

PROTOCOL_VERSION = "0.1.0-sprint0"
