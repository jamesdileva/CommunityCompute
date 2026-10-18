"""Workload reference implementations (coordinator side).

The coordinator re-derives expected values deterministically — it never
trusts worker output (architecture §18). Workload-specific math lives
behind this registry so the verification path stays generic.
"""

from app.services.workloads import embeddings, hello_compute, image_generate, stats_range
from packages.protocol.workloads import (
    WorkloadDefinition,
    definition_for,
    sign_definition,
)

# Sprint 21 allowlist: the only workload types this coordinator will run.
# Both submit-time validation and verification dispatch consult this set —
# anything else is rejected before it can reach a worker.
# Sprint 33 adds image_generate: the first GPU-gated type, so a mixed fleet
# can run different workload types on different hardware classes at once.
KNOWN_WORKLOAD_TYPES = frozenset(
    {"hello_compute", "stats_range", "embeddings", "image_generate"}
)


def is_known_workload(workload_type: str) -> bool:
    return workload_type in KNOWN_WORKLOAD_TYPES


def definition(workload_type: str) -> WorkloadDefinition | None:
    """The signed workload definition for a type (Sprint 30)."""
    return definition_for(workload_type)


def workload_version(workload_type: str) -> str:
    """Version of the pinned workload definition, or "" for unknown types."""
    defn = definition_for(workload_type)
    return defn.version if defn else ""


def signed_manifest(workload_type: str, key: str) -> dict | None:
    """The definition manifest + its signature, ready to serve (Sprint 30)."""
    defn = definition_for(workload_type)
    if defn is None:
        return None
    manifest = defn.to_manifest()
    return {**manifest, "signature": sign_definition(manifest, key)}


def expected(workload_type: str, op: str, range_start: int, range_end: int,
             params: dict | None = None):
    """Expected value for a unit, or ValueError for unknown types/ops."""
    if workload_type == "hello_compute":
        return hello_compute.compute(op, range_start, range_end)
    if workload_type == "stats_range":
        return stats_range.compute(range_start, range_end)
    if workload_type == "embeddings":
        dim = (params or {}).get("dim", 128)
        return embeddings.compute_batch(range_start, range_end, dim)
    if workload_type == "image_generate":
        size, seed = image_generate.normalize_params(params)
        return image_generate.compute(range_start, range_end, size, seed)
    raise ValueError(f"unknown workload type {workload_type!r}")


def output_hash(workload_type: str, op: str, value: object, params: dict | None = None) -> str:
    if workload_type == "hello_compute":
        return hello_compute.output_hash(op, value)
    if workload_type in ("stats_range", "embeddings", "image_generate"):
        module = {
            "stats_range": stats_range,
            "embeddings": embeddings,
            "image_generate": image_generate,
        }[workload_type]
        return module.output_hash(value)
    raise ValueError(f"unknown workload type {workload_type!r}")
