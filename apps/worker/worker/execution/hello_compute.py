"""Workload execution (Sprint 6): deterministic hello-compute + fail-closed registry.

The executor validates before executing: protocol version, known workload
type, sane range, and payload sanity. Anything it doesn't understand is
rejected (fail closed — architecture §9).
"""

import hashlib
import time
from dataclasses import dataclass

from packages.protocol import version_supported


def compute(op: str, range_start: int, range_end: int) -> int | str:
    """Deterministic result for a range. Must stay identical to the coordinator's copy."""
    if op == "sum":
        return (range_start + range_end) * (range_end - range_start + 1) // 2
    if op == "hash":
        return hashlib.sha256(f"{range_start}:{range_end}".encode()).hexdigest()
    raise ValueError(f"unknown hello_compute op: {op!r}")


def output_hash(op: str, value: int | str) -> str:
    return hashlib.sha256(f"{op}:{value}".encode()).hexdigest()


class RejectedUnit(Exception):
    """Raised when a unit fails validation — worker reports failure upward."""


@dataclass
class UnitResult:
    status: str  # "completed" | "failed"
    value: object | None = None
    output_hash: str | None = None
    error: str | None = None
    execution_ms: float | None = None


class HelloComputeExecutor:
    workload_type = "hello_compute"

    def can_execute(self, assignment: dict) -> tuple[bool, str | None]:
        if not version_supported(assignment.get("protocol_version")):
            return False, f"unsupported protocol version {assignment.get('protocol_version')!r}"
        if assignment.get("workload_type") != self.workload_type:
            return False, f"unknown workload type {assignment.get('workload_type')!r}"
        start, end = assignment.get("range_start"), assignment.get("range_end")
        if not isinstance(start, int) or not isinstance(end, int):
            return False, "range must be integers"
        if start < 1 or end < start:
            return False, f"invalid range {start}..{end}"
        op = (assignment.get("params") or {}).get("op", "sum")
        if op not in {"sum", "hash"}:
            return False, f"unsupported op {op!r}"
        return True, None

    def execute(self, assignment: dict) -> UnitResult:
        ok, reason = self.can_execute(assignment)
        if not ok:
            return UnitResult(status="failed", error=f"rejected: {reason}")
        op = (assignment.get("params") or {}).get("op", "sum")
        started = time.perf_counter()
        try:
            value = compute(op, assignment["range_start"], assignment["range_end"])
        except Exception as exc:  # noqa: BLE001 - any failure must be reported, not crash
            return UnitResult(status="failed", error=f"execution error: {exc}")
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        return UnitResult(
            status="completed",
            value=value,
            output_hash=output_hash(op, value),
            execution_ms=elapsed_ms,
        )


_REGISTRY = {HelloComputeExecutor.workload_type: HelloComputeExecutor()}


def execute_unit(assignment: dict) -> UnitResult:
    """Dispatch to a registered executor; unknown types fail closed."""
    executor = _REGISTRY.get(assignment.get("workload_type", ""))
    if executor is None:
        return UnitResult(
            status="failed",
            error=f"no executor for workload type {assignment.get('workload_type')!r}",
        )
    return executor.execute(assignment)
