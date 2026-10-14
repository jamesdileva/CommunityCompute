"""Workload reference implementations (coordinator side).

The coordinator re-derives expected values deterministically — it never
trusts worker output (architecture §18). Workload-specific math lives
behind this registry so the verification path stays generic.
"""

from app.services.workloads import embeddings, hello_compute, stats_range

# Sprint 21 allowlist: the only workload types this coordinator will run.
# Both submit-time validation and verification dispatch consult this set —
# anything else is rejected before it can reach a worker.
KNOWN_WORKLOAD_TYPES = frozenset({"hello_compute", "stats_range", "embeddings"})


def is_known_workload(workload_type: str) -> bool:
    return workload_type in KNOWN_WORKLOAD_TYPES


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
    raise ValueError(f"unknown workload type {workload_type!r}")


def output_hash(workload_type: str, op: str, value: object, params: dict | None = None) -> str:
    if workload_type == "hello_compute":
        return hello_compute.output_hash(op, value)
    if workload_type in ("stats_range", "embeddings"):
        module = stats_range if workload_type == "stats_range" else embeddings
        return module.output_hash(value)
    raise ValueError(f"unknown workload type {workload_type!r}")
