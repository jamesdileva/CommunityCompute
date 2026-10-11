"""hello-compute: deterministic reference implementation (coordinator side).

Both sides compute the same pure function over a unit's range, which is what
makes verification exact: the coordinator knows the expected result without
trusting the worker (architecture §18, implementation-guide §11).
"""

import hashlib


def compute(op: str, range_start: int, range_end: int) -> int | str:
    """Deterministic result for a range. Raises ValueError on unknown op."""
    if op == "sum":
        # sum(start..end) inclusive
        return (range_start + range_end) * (range_end - range_start + 1) // 2
    if op == "hash":
        return hashlib.sha256(f"{range_start}:{range_end}".encode()).hexdigest()
    raise ValueError(f"unknown hello_compute op: {op!r}")


def output_hash(op: str, value: int | str) -> str:
    """Stable hash of a worker result; corruption is detected by recomputing."""
    return hashlib.sha256(f"{op}:{value}".encode()).hexdigest()
