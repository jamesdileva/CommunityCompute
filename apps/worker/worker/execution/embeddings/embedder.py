"""Embedder adapter interface (Sprint 14).

AI runtimes are adapter-based per architecture §22 — this package never
hardcodes a model/runtime. `HashingEmbedder` is the prototype implementation:
deterministic feature-hashing of tokens into a fixed-dim, L2-normalized
vector (the classic sklearn HashingVectorizer construction). A future
SentenceTransformerEmbedder / ONNXEmbedder / OllamaEmbedder slots in behind
the same `embed_documents` signature once the model cache exists (Sprint 15).
"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def corpus_text(index: int) -> str:
    """Deterministic synthetic corpus (document i is identical everywhere).

    Prototype stand-in for a real corpus: no fetch layer yet (arrives with
    model distribution in Sprint 15), but both sides derive the same text,
    so verification stays exact.
    """
    topic = index % 12
    return (
        f"document {index} topic {topic} "
        f"community compute worker index {index} sample text {index % 7}"
    )


class Embedder(ABC):
    """Adapter: turns documents into fixed-dim float vectors."""

    dim: int = 128

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """One vector per input document, L2-normalized."""


class HashingEmbedder(Embedder):
    """Deterministic, dependency-free embedder (feature hashing + L2 norm)."""

    def __init__(self, dim: int = 128) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha256(token.encode()).digest()
            slot = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] & 1 == 0 else -1.0
            vector[slot] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0.0:
            return vector  # empty text → zero vector (allowed)
        return [round(v / norm, 6) for v in vector]


def default_embedder(dim: int = 128) -> Embedder:
    return HashingEmbedder(dim=dim)
