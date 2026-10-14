"""Assignment integrity seal (Sprint 21).

HMAC-SHA256 over the canonical assignment payload. The coordinator signs
every claim; the worker verifies before executing and refuses on mismatch.

Prototype honesty: this is a *shared-secret* seal, not asymmetric signing —
both sides configure the same key. It proves integrity (tamper-evident
assignments) but not origin; public-key manifests arrive with the sandbox
milestone (Sprint 22+). Never ship the dev key anywhere but test networks.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

DEV_SIGNING_KEY = "dev-insecure-signing-key-do-not-use-in-production"

# Fields covered by the seal. Keep this list stable: adding a field changes
# every signature, which is exactly the tamper-evidence we want.
SEALED_FIELDS = (
    "work_unit_id",
    "job_id",
    "workload_type",
    "range_start",
    "range_end",
    "params",
)


def canonical_payload(assignment: dict[str, Any]) -> bytes:
    """Deterministic bytes for exactly the sealed fields (key order irrelevant)."""
    picked = {k: assignment.get(k) for k in SEALED_FIELDS}
    return json.dumps(picked, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_manifest(assignment: dict[str, Any], key: str) -> str:
    return hmac.new(key.encode("utf-8"), canonical_payload(assignment),
                    hashlib.sha256).hexdigest()


def verify_manifest(assignment: dict[str, Any], signature: object, key: str) -> bool:
    if not isinstance(signature, str) or not signature:
        return False
    try:
        expected = sign_manifest(assignment, key)
    except Exception:  # noqa: BLE001 - unserializable payload: treat as tampered
        return False
    return hmac.compare_digest(expected, signature)
