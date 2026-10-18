"""image-generate workload (Sprint 33): the first GPU-gated executor.

Same deterministic-stub pattern as the other executors (no bundled AI
runtime), but its advertising requirements include a GPU, so the scheduler
only offers this work to GPU-capable workers while the CPU workloads keep
running elsewhere — a mixed fleet processes both types at once.
"""

import hashlib

from worker.execution.executor import ExecutorMetadata, UnitResult, WorkloadExecutor

DEFAULT_SIZE = 32
DEFAULT_SEED = "cc"


def tile(seed: str, index: int, size: int) -> str:
    """Deterministic hex digest for one pseudo-image tile.

    Must stay identical to the coordinator's image_generate.tile so results
    verify exactly.
    """
    return hashlib.sha256(f"{seed}:{index}:{size}".encode()).hexdigest()


def compute(range_start: int, range_end: int, size: int = DEFAULT_SIZE,
            seed: str = DEFAULT_SEED) -> dict:
    tiles = [tile(seed, i, size) for i in range(range_start, range_end + 1)]
    checksum = hashlib.sha256("".join(tiles).encode()).hexdigest()
    return {"size": size, "tiles": len(tiles), "checksum": checksum}


class ImageGenerateExecutor(WorkloadExecutor):
    workload_type = "image_generate"

    @property
    def metadata(self) -> ExecutorMetadata:
        return ExecutorMetadata(
            workload_type=self.workload_type,
            version="1",
            description="deterministic pseudo-image tiles for a range of ids (GPU-gated)",
            requirements={"gpu": True, "min_vram_mb": 2048},
            deterministic=True,
        )

    def execute(self, assignment: dict) -> UnitResult:
        params = assignment.get("params") or {}
        size = params.get("size", DEFAULT_SIZE)
        seed = params.get("seed", DEFAULT_SEED)
        if not isinstance(size, int) or size <= 0:
            return UnitResult(status="failed", error=f"invalid size {size!r}")
        if not isinstance(seed, str) or not seed:
            return UnitResult(status="failed", error=f"invalid seed {seed!r}")
        value = compute(assignment["range_start"], assignment["range_end"], size, seed)
        return UnitResult(status="completed", value=value, execution_ms=None)

    def verify(self, result: UnitResult, assignment: dict) -> tuple[bool, str | None]:
        """Local re-computation of the tile checksum before submission."""
        if result.status != "completed" or not isinstance(result.value, dict):
            return False, result.error or "expected size+tiles+checksum payload"
        params = assignment.get("params") or {}
        try:
            expected = compute(
                assignment["range_start"],
                assignment["range_end"],
                params.get("size", DEFAULT_SIZE),
                params.get("seed", DEFAULT_SEED),
            )
        except (TypeError, ValueError) as exc:
            return False, f"invalid params: {exc}"
        if result.value != expected:
            return False, f"image mismatch: expected {expected!r}, got {result.value!r}"
        return True, None
