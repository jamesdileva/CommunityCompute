"""Signed workload definitions (Sprint 30).

A **workload definition** is the immutable contract for a workload type: its
name, version, expected parameters, and resource requirements. It is the
thing the scheduler, the customer, and the worker must agree on before any
work happens.

Signing model (prototype-honest, mirrors ``signing.py``): HMAC-SHA256 with the
shared workload key. It is tamper-evidence, not asymmetric origin — but it
makes a *divergent contract* impossible to run silently:

- the coordinator serves definitions signed with the key;
- every worker re-derives its **local** definition, and refuses an assignment
  whose ``workload_version`` differs or whose ``workload_signature`` doesn't
  match the local definition. Coordinator and worker that disagree about a
  workload's contract fail closed instead of executing something unexpected.

Public-key manifests replace the shared secret with the sandbox/public beta
milestone; the message shape here stays the same.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class WorkloadDefinition:
    name: str
    version: str
    description: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    requirements: dict[str, Any] = field(default_factory=dict)
    deterministic: bool = True

    def to_manifest(self) -> dict[str, Any]:
        """Plain dict form used for signing and serving."""
        return asdict(self)


# The catalog is the single source of truth for what workloads exist and what
# contract they carry. Version bumps whenever the contract changes.
WORKLOAD_CATALOG: dict[str, WorkloadDefinition] = {
    "hello_compute": WorkloadDefinition(
        name="hello_compute",
        version="1",
        description="Deterministic sum/hash over an inclusive integer range.",
        params={"op": "sum | hash"},
        requirements={"cpu_cores": 1},
    ),
    "stats_range": WorkloadDefinition(
        name="stats_range",
        version="1",
        description="Count/mean/min/max/sum over an inclusive integer range.",
        params={},
        requirements={"cpu_cores": 1},
    ),
    "embeddings": WorkloadDefinition(
        name="embeddings",
        version="1",
        description="Deterministic pseudo-embeddings for a range of ids.",
        params={"dim": "embedding dimension (default 128)"},
        requirements={"cpu_cores": 1},
    ),
}


def definition_for(workload_type: str) -> WorkloadDefinition | None:
    return WORKLOAD_CATALOG.get(workload_type or "")


def canonical_definition(manifest: dict[str, Any]) -> bytes:
    """Deterministic bytes for a definition manifest (key order irrelevant)."""
    return json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_definition(manifest: dict[str, Any], key: str) -> str:
    return hmac.new(key.encode("utf-8"), canonical_definition(manifest),
                    hashlib.sha256).hexdigest()


def verify_definition(manifest: dict[str, Any], signature: object, key: str) -> bool:
    if not isinstance(signature, str) or not signature:
        return False
    try:
        expected = sign_definition(manifest, key)
    except Exception:  # noqa: BLE001 - unserializable manifest: treat as untrusted
        return False
    return hmac.compare_digest(expected, signature)


def attach_signed_definition(assignment: dict[str, Any], key: str) -> dict[str, Any]:
    """Return `assignment` with the signed definition fields filled in.

    Adds ``workload_version`` + ``workload_signature`` for the named workload
    (no-op for an unknown type, which the worker would refuse anyway).
    """
    definition = definition_for(assignment.get("workload_type", ""))
    if definition is None:
        return dict(assignment)
    manifest = definition.to_manifest()
    return {
        **assignment,
        "workload_version": definition.version,
        "workload_signature": sign_definition(manifest, key),
    }
