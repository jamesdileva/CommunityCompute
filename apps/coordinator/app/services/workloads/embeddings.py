"""Embeddings reference (coordinator side): same math as the worker adapter.

Re-derives the expected batch vectors so the coordinator verifies results
exactly (architecture §18). Deterministic feature hashing means the
reference is cheap and dependency-free on the coordinator too.
"""

import hashlib
import math
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def corpus_text(index: int) -> str:
    """Must stay identical to worker.execution.embeddings.embedder.corpus_text."""
    topic = index % 12
    return (
        f"document {index} topic {topic} "
        f"community compute worker index {index} sample text {index % 7}"
    )


def embed(text: str, dim: int = 128) -> list[float]:
    vector = [0.0] * dim
    for token in _TOKEN_RE.findall(text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        slot = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] & 1 == 0 else -1.0
        vector[slot] += sign
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        return vector
    return [round(v / norm, 6) for v in vector]


def compute_batch(range_start: int, range_end: int, dim: int = 128) -> dict:
    return {
        "dim": dim,
        "vectors": [embed(corpus_text(i), dim) for i in range(range_start, range_end + 1)],
    }


def output_hash(value: object) -> str:
    return hashlib.sha256(repr(value).encode()).hexdigest()
