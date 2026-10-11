"""stats-range reference (coordinator side): same math as the worker executor."""


def compute(range_start: int, range_end: int) -> dict:
    count = range_end - range_start + 1
    return {
        "count": count,
        "sum": (range_start + range_end) * count // 2,
        "max": range_end,
        "min": range_start,
    }


def output_hash(value: object) -> str:
    import hashlib

    return hashlib.sha256(repr(value).encode()).hexdigest()
