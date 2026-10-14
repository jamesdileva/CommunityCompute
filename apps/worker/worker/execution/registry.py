"""Executor registry (Sprint 13): dispatch + lifecycle runner.

The registry is the only place that knows about individual workloads —
everything upstream (scheduler, coordinator protocol) stays generic.

Sprint 21 hardening, applied here so every workload gets it uniformly:
- allowlist: only registered types execute (unknown → failed, never run).
- integrity: the coordinator's HMAC seal is verified before anything else;
  a missing or mismatched `manifest_signature` refuses the unit outright.
- isolation: each unit runs with a fresh temporary work directory, injected
  as `assignment["work_dir"]` and deleted afterwards — even on failure.
- time-box: `execute()` runs under `time_limit` seconds. On expiry the unit
  fails with "time limit exceeded"; the abandoned thread is NOT killed
  (documented prototype limit — Sprint 22's sandbox does preemptive kill).
"""

import os
import tempfile
import threading

from packages.protocol.signing import verify_manifest

from worker.execution.embeddings.executor import EmbeddingsExecutor
from worker.execution.executor import UnitResult, WorkloadExecutor
from worker.execution.hello_compute import HelloComputeExecutor
from worker.execution.stats_range import StatsRangeExecutor

_EXECUTORS: dict[str, WorkloadExecutor] = {
    HelloComputeExecutor.workload_type: HelloComputeExecutor(),
    StatsRangeExecutor.workload_type: StatsRangeExecutor(),
    EmbeddingsExecutor.workload_type: EmbeddingsExecutor(),
}


def executor_for(workload_type: str) -> WorkloadExecutor | None:
    return _EXECUTORS.get(workload_type or "")


def list_executors() -> list[WorkloadExecutor]:
    return list(_EXECUTORS.values())


def supported_runtimes() -> list[str]:
    """Workload types this worker can execute (advertised in capabilities)."""
    return sorted(_EXECUTORS)


DEFAULT_UNIT_TIME_LIMIT = 300.0


def signing_key() -> str:
    """Shared HMAC key (Sprint 21 prototype): env or dev default.

    Must match the coordinator's WORKLOAD_SIGNING_KEY or every unit is
    refused — fail closed, loudly.
    """
    from packages.protocol.signing import DEV_SIGNING_KEY

    return os.environ.get("WORKLOAD_SIGNING_KEY", DEV_SIGNING_KEY)


def run_unit(
    assignment: dict,
    capabilities: dict | None = None,
    *,
    work_root: str | None = None,
    time_limit: float = DEFAULT_UNIT_TIME_LIMIT,
) -> UnitResult:
    """Registry entry used by the worker loop: unknown types fail closed."""
    executor = executor_for(assignment.get("workload_type", ""))
    if executor is None:
        return UnitResult(
            status="failed",
            error=f"no executor for workload type {assignment.get('workload_type')!r}",
        )
    if not verify_manifest(assignment, assignment.get("manifest_signature"), signing_key()):
        return UnitResult(
            status="failed",
            error="refused: manifest signature missing or invalid",
        )
    try:
        work_dir_ctx = tempfile.TemporaryDirectory(prefix="unit-", dir=work_root)
    except OSError as exc:
        # The never-raises contract holds even for environment failures:
        # a missing work root fails the unit, never the worker loop.
        return UnitResult(status="failed", error=f"work directory unavailable: {exc}")
    with work_dir_ctx as work_dir:
        scoped = {**assignment, "work_dir": work_dir}
        return _run_timed(executor, scoped, capabilities, time_limit)


def _run_timed(
    executor: WorkloadExecutor,
    assignment: dict,
    capabilities: dict | None,
    time_limit: float,
) -> UnitResult:
    # Daemon thread + join(timeout): on expiry the unit fails immediately and
    # the abandoned thread is left to die on its own (it can NOT be killed —
    # documented prototype limit; Sprint 22's sandbox does preemptive kill).
    box: dict[str, UnitResult] = {}

    def _call() -> None:
        try:
            box["result"] = executor.run(assignment, capabilities)
        except Exception as exc:  # noqa: BLE001 - belt and braces; run() never raises
            box["result"] = UnitResult(status="failed", error=f"execution error: {exc}")

    thread = threading.Thread(target=_call, name="unit-exec", daemon=True)
    thread.start()
    thread.join(timeout=time_limit)
    if thread.is_alive():
        return UnitResult(
            status="failed",
            error=f"time limit exceeded ({time_limit}s); unit abandoned, "
            "see Sprint 22 for preemptive kill",
        )
    return box.get("result") or UnitResult(status="failed", error="executor returned nothing")
