"""Workload reference implementations (coordinator side).

The coordinator re-derives expected values deterministically — it never
trusts worker output (architecture §18). Workload-specific math lives
behind this registry so the verification path stays generic.
"""

from app.services.workloads import hello_compute, stats_range


def expected(workload_type: str, op: str, range_start: int, range_end: int):
    """Expected value for a unit, or ValueError for unknown types/ops."""
    if workload_type == "hello_compute":
        return hello_compute.compute(op, range_start, range_end)
    if workload_type == "stats_range":
        return stats_range.compute(range_start, range_end)
    raise ValueError(f"unknown workload type {workload_type!r}")


def output_hash(workload_type: str, op: str, value: object) -> str:
    if workload_type == "hello_compute":
        return hello_compute.output_hash(op, value)
    if workload_type == "stats_range":
        return stats_range.output_hash(value)
    raise ValueError(f"unknown workload type {workload_type!r}")
