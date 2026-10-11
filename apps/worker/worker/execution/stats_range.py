"""stats-range workload (Sprint 13): second executor, dict-shaped results.

Proves the pipeline is workload-agnostic: same claim endpoint, same result
verification, different value shape and different local verify() logic.
"""

from worker.execution.executor import ExecutorMetadata, UnitResult, WorkloadExecutor


def compute(range_start: int, range_end: int) -> dict:
    """{count, sum, max, min} for an inclusive integer range."""
    count = range_end - range_start + 1
    return {
        "count": count,
        "sum": (range_start + range_end) * count // 2,
        "max": range_end,
        "min": range_start,
    }


class StatsRangeExecutor(WorkloadExecutor):
    workload_type = "stats_range"

    @property
    def metadata(self) -> ExecutorMetadata:
        return ExecutorMetadata(
            workload_type=self.workload_type,
            version="1",
            description="per-range count/sum/max/min statistics (dict payload)",
            requirements={"cpu_cores": 1},
            deterministic=True,
        )

    def execute(self, assignment: dict) -> UnitResult:
        value = compute(assignment["range_start"], assignment["range_end"])
        return UnitResult(status="completed", value=value, execution_ms=None)

    def verify(self, result: UnitResult, assignment: dict) -> tuple[bool, str | None]:
        """Local re-computation of every field before submission."""
        if result.status != "completed" or not isinstance(result.value, dict):
            return False, result.error or "expected dict stats payload"
        expected = compute(assignment["range_start"], assignment["range_end"])
        if result.value != expected:
            return False, f"stats mismatch: expected {expected!r}, got {result.value!r}"
        return True, None
