"""Image-generation reference (coordinator side): same math as the worker.

Sprint 33: the first GPU-gated workload. Like every other workload in this
prototype the actual "generation" is a deterministic, dependency-free stub
(no AI runtime is bundled — see AGENTS.md non-goals), so the coordinator can
re-derive the exact expected tiles and verify results bit-for-bit. The GPU
requirement lives on the workload definition and is what routes the work to a
different hardware class from the CPU workloads.
"""

import hashlib

DEFAULT_SIZE = 32
DEFAULT_SEED = "cc"


def tile(seed: str, index: int, size: int) -> str:
    """Deterministic hex digest for one pseudo-image tile.

    Must stay identical to worker.execution.image_generate.tile.
    """
    return hashlib.sha256(f"{seed}:{index}:{size}".encode()).hexdigest()


def normalize_params(params: dict | None) -> tuple[int, str]:
    params = params or {}
    size = params.get("size", DEFAULT_SIZE)
    if not isinstance(size, int) or size <= 0:
        raise ValueError(f"invalid size {size!r}")
    seed = params.get("seed", DEFAULT_SEED)
    if not isinstance(seed, str) or not seed:
        raise ValueError(f"invalid seed {seed!r}")
    return size, seed


def compute(range_start: int, range_end: int, size: int = DEFAULT_SIZE,
            seed: str = DEFAULT_SEED) -> dict:
    tiles = [tile(seed, i, size) for i in range(range_start, range_end + 1)]
    checksum = hashlib.sha256("".join(tiles).encode()).hexdigest()
    return {"size": size, "tiles": len(tiles), "checksum": checksum}


def output_hash(value: object) -> str:
    return hashlib.sha256(repr(value).encode()).hexdigest()
