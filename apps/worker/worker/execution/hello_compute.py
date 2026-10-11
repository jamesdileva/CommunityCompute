"""hello-compute workload (Sprints 6-13): deterministic scalar results.

Refactored onto the WorkloadExecutor interface in Sprint 13; the public
`compute`/`output_hash` functions stay stable (tests + coordinator parity).
"""

import hashlib

from worker.execution.executor import ExecutorMetadata, UnitResult, WorkloadExecutor


def compute(op: str, range_start: int, range_end: int) -> int | str:
    """Deterministic result for a range. Must stay identical to the coordinator's copy."""
    if op == "sum":
        return (range_start + range_end) * (range_end - range_start + 1) // 2
    if op == "hash":
        return hashlib.sha256(f"{range_start}:{range_end}".encode()).hexdigest()
    raise ValueError(f"unknown hello_compute op: {op!r}")


def output_hash(op: str, value: int | str) -> str:
    return hashlib.sha256(f"{op}:{value}".encode()).hexdigest()


class HelloComputeExecutor(WorkloadExecutor):
    workload_type = "hello_compute"

    @property
    def metadata(self) -> ExecutorMetadata:
        return ExecutorMetadata(
            workload_type=self.workload_type,
            version="1",
            description="deterministic deterministic sum/hash over integer ranges",
            requirements={},  # runs anywhere
            deterministic=True,
        )

    def valid_params(self, params: dict) -> bool:
        return (params or {}).get("op", "sum") in {"sum", "hash"}

    def execute(self, assignment: dict) -> UnitResult:
        op = (assignment.get("params") or {}).get("op", "sum")
        try:
            value = compute(op, assignment["range_start"], assignment["range_end"])
        except ValueError as exc:
            return UnitResult(status="failed", error=str(exc))
        return UnitResult(
            status="completed",
            value=value,
            output_hash=output_hash(op, value),
            execution_ms=None,  # filled by the runner's timer
        )
