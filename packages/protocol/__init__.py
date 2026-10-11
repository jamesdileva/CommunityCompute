"""CommunityCompute protocol: versioned Worker↔Coordinator messages.

Sprint 6 introduces message names + a compatibility check. Full Pydantic
message classes stay here as the contract; each app imports PROTOCOL_VERSION
via its own path bootstrap until the package is pip-installed (prototype).
"""

PROTOCOL_VERSION = "0.1.0-sprint6"

# Message identifiers (implementation-guide §4 sketch, plus Sprint 6 work flow)
WORKER_REGISTRATION = "WorkerRegistration"
HEARTBEAT = "Heartbeat"
WORK_ASSIGNMENT = "WorkAssignment"
WORK_RESULT = "WorkResult"

SUPPORTED_MESSAGE_VERSIONS = frozenset({PROTOCOL_VERSION})


def version_supported(version: object) -> bool:
    """Fail-closed check: unknown protocol versions are rejected, not guessed."""
    return isinstance(version, str) and version in SUPPORTED_MESSAGE_VERSIONS
