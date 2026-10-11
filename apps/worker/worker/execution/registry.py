"""Executor registry (Sprint 13): dispatch + lifecycle runner.

The registry is the only place that knows about individual workloads —
everything upstream (scheduler, coordinator protocol) stays generic.
"""

from worker.execution.executor import UnitResult, WorkloadExecutor
from worker.execution.hello_compute import HelloComputeExecutor
from worker.execution.stats_range import StatsRangeExecutor

_EXECUTORS: dict[str, WorkloadExecutor] = {
    HelloComputeExecutor.workload_type: HelloComputeExecutor(),
    StatsRangeExecutor.workload_type: StatsRangeExecutor(),
}


def executor_for(workload_type: str) -> WorkloadExecutor | None:
    return _EXECUTORS.get(workload_type or "")


def list_executors() -> list[WorkloadExecutor]:
    return list(_EXECUTORS.values())


def supported_runtimes() -> list[str]:
    """Workload types this worker can execute (advertised in capabilities)."""
    return sorted(_EXECUTORS)


def run_unit(assignment: dict, capabilities: dict | None = None) -> UnitResult:
    """Registry entry used by the worker loop: unknown types fail closed."""
    executor = executor_for(assignment.get("workload_type", ""))
    if executor is None:
        return UnitResult(
            status="failed",
            error=f"no executor for workload type {assignment.get('workload_type')!r}",
        )
    return executor.run(assignment, capabilities)
