"""Model manifests (Sprint 15).

A manifest describes a fetchable, verifiable artifact for a workload: where
it comes from, what its sha256 must be, and how big it is. The prototype's
model-backed executors ship tiny inline bundles — the fetch/verify/reuse
machinery is identical whether the artifact is 200 bytes or a 2 GB weight
file (only the source string and size differ).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

# The prototype embedding artifact: a versioned bundle whose content is the
# manifest identity itself (deterministic across all machines).
_EMBEDDING_BUNDLE = b"hashing-embedder/v1"

_SHA256_LEN = 64


@dataclass(frozen=True)
class ModelManifest:
    name: str
    version: str
    source: str  # "inline:<text>", "file:<path>", or "http(s)://..."
    sha256: str  # hex digest of the artifact bytes
    size_bytes: int

    @property
    def key(self) -> str:
        return f"{self.name}@{self.version}"

    def verify(self, data: bytes) -> bool:
        return hashlib.sha256(data).hexdigest() == self.sha256 and len(data) == self.size_bytes


def manifest_for(workload_type: str) -> ModelManifest | None:
    """The model a workload needs (None = no model dependency)."""
    if workload_type == "embeddings":
        digest = hashlib.sha256(_EMBEDDING_BUNDLE).hexdigest()
        return ModelManifest(
            name="hashing-embedder",
            version="1",
            source="inline:hashing-embedder/v1",
            sha256=digest,
            size_bytes=len(_EMBEDDING_BUNDLE),
        )
    return None


def model_requirement(manifest: ModelManifest) -> str:
    """Requirement value used in job requirements + claim preference."""
    return manifest.key
