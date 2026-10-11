"""WorkloadExecutor interface (Sprint 13, implementation-guide §21).

The scheduler never learns a workload's internals. An executor declares its
own metadata (including requirements the coordinator filters on), validates
its own units, and runs a fixed lifecycle:

    prepare -> can_execute -> execute -> verify -> cleanup

Every stage failure becomes a `failed` UnitResult — the worker reports it
upward instead of crashing or silently skipping.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from packages.protocol import version_supported


@dataclass
class UnitResult:
    status: str  # "completed" | "failed"
    value: object | None = None
    output_hash: str | None = None
    error: str | None = None
    execution_ms: float | None = None


@dataclass
class ExecutorMetadata:
    """Declarative workload facts (scheduler/registry visible, not logic)."""

    workload_type: str
    version: str = "1"
    description: str = ""
    requirements: dict[str, Any] = field(default_factory=dict)
    deterministic: bool = True


class WorkloadExecutor(ABC):
    workload_type: str = ""

    @property
    def metadata(self) -> ExecutorMetadata:
        return ExecutorMetadata(workload_type=self.workload_type)

    # ---- validation -----------------------------------------------------
    def can_execute(
        self, assignment: dict, capabilities: dict | None = None
    ) -> tuple[bool, str | None]:
        """Fail closed: protocol, workload type, range sanity, payload, resource fit."""
        if not version_supported(assignment.get("protocol_version")):
            return False, f"unsupported protocol version {assignment.get('protocol_version')!r}"
        if assignment.get("workload_type") != self.workload_type:
            return False, f"unknown workload type {assignment.get('workload_type')!r}"
        start, end = assignment.get("range_start"), assignment.get("range_end")
        if not isinstance(start, int) or not isinstance(end, int):
            return False, "range must be integers"
        if start < 1 or end < start:
            return False, f"invalid range {start}..{end}"
        if not self.valid_params((assignment.get("params") or {})):
            return False, "invalid params"
        ok, reason = self._fits_capabilities(capabilities)
        if not ok:
            return False, reason
        return True, None

    def valid_params(self, params: dict) -> bool:
        return True

    def _fits_capabilities(
        self, capabilities: dict | None
    ) -> tuple[bool, str | None]:
        """Resource fit from declared requirements (architecture §10 subset)."""
        if capabilities is None:
            return True, None  # compatibility handled by the scheduler when known
        requirements = self.metadata.requirements or {}
        if requirements.get("gpu"):
            gpus = capabilities.get("gpus") or []
            vendor = requirements.get("gpu_vendor")
            min_vram = requirements.get("min_vram_mb")
            for gpu in gpus:
                if vendor and str(gpu.get("vendor", "")).lower() != str(vendor).lower():
                    continue
                if min_vram is not None:
                    have_vram = gpu.get("vram_mb")
                    if have_vram is None or have_vram < min_vram:
                        continue
                return True, None
            return False, "declared gpu requirement not satisfied"
        return True, None

    # ---- lifecycle stages ------------------------------------------------
    @abstractmethod
    def execute(self, assignment: dict) -> UnitResult:
        """Run the unit. Must not raise for bad input — return a failed result."""

    def prepare(self, assignment: dict) -> None:
        """Load models/resolve inputs. Default: nothing to prepare."""

    def verify(self, result: UnitResult, assignment: dict) -> tuple[bool, str | None]:
        """Worker-side local verification. Default: trust completed results."""
        if result.status != "completed":
            return False, result.error or "execution did not complete"
        return True, None

    def cleanup(self) -> None:
        """Release scratch state. Default: nothing to clean."""

    # ---- runner ----------------------------------------------------------
    def run(self, assignment: dict, capabilities: dict | None = None) -> UnitResult:
        """Full lifecycle: prepare → validate → execute → verify → cleanup.

        Never raises; any stage failure becomes a `failed` UnitResult.
        """
        try:
            self.prepare(assignment)
        except Exception as exc:  # noqa: BLE001
            return UnitResult(status="failed", error=f"prepare failed: {exc}")
        ok, reason = self.can_execute(assignment, capabilities)
        if not ok:
            return UnitResult(status="failed", error=f"rejected: {reason}")
        started = perf_counter()
        try:
            result = self.execute(assignment)
        except Exception as exc:  # noqa: BLE001
            result = UnitResult(status="failed", error=f"execution error: {exc}")
        if result.execution_ms is None:
            result.execution_ms = round((perf_counter() - started) * 1000, 3)
        # verify BEFORE cleanup: the verifier may still need scratch state
        try:
            ok, reason = self.verify(result, assignment)
            if not ok:
                result.status = "failed"
                result.value = None
                result.output_hash = None
                result.error = reason
        except Exception as exc:  # noqa: BLE001
            result.status = "failed"
            result.value = None
            result.output_hash = None
            result.error = f"verify crashed: {exc}"
        try:
            self.cleanup()
        except Exception:  # noqa: BLE001 - cleanup must never break the result path
            pass
        return result


def range_is_sane(start: object, end: object) -> bool:
    return isinstance(start, int) and isinstance(end, int) and start >= 1 and end >= start
