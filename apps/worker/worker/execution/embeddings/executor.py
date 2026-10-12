"""Embeddings workload (Sprint 14; Sprint 15: model-cache-backed prepare)."""

from worker.execution.embeddings.embedder import HashingEmbedder, corpus_text
from worker.execution.executor import ExecutorMetadata, UnitResult, WorkloadExecutor
from worker.models.cache import CacheError, ModelCache, default_cache_dir
from worker.models.manifest import manifest_for

DEFAULT_DIM = 128


class EmbeddingsExecutor(WorkloadExecutor):
    workload_type = "embeddings"

    @property
    def metadata(self) -> ExecutorMetadata:
        return ExecutorMetadata(
            workload_type=self.workload_type,
            version="1",
            description="L2-normalized feature-hash embeddings over synthetic corpus batches",
            requirements={},  # CPU-runnable: both prototype machines qualify
            deterministic=True,
        )

    def prepare(self, assignment: dict) -> None:
        """Ensure the workload's model artifact is cached (fetch-once, Sprint 15)."""
        manifest = manifest_for(self.workload_type)
        if manifest is None:
            return
        try:
            cache_hit, _data = ModelCache(default_cache_dir()).ensure(manifest)
        except (CacheError, OSError) as exc:
            raise RuntimeError(f"model cache ensure failed: {exc}") from exc
        self._last_cache_hit = cache_hit  # consumed by execute() for metrics

    def execute(self, assignment: dict) -> UnitResult:
        dim = (assignment.get("params") or {}).get("dim", DEFAULT_DIM)
        if not isinstance(dim, int) or dim <= 0:
            return UnitResult(status="failed", error=f"invalid dim {dim!r}")
        cache_hit = getattr(self, "_last_cache_hit", False)
        embedder = HashingEmbedder(dim=dim)
        start, end = assignment["range_start"], assignment["range_end"]
        texts = [corpus_text(i) for i in range(start, end + 1)]
        vectors = embedder.embed_documents(texts)
        manifest = manifest_for(self.workload_type)
        return UnitResult(
            status="completed",
            value={"dim": dim, "vectors": vectors},
            metrics={
                "docs": len(texts),
                "dim": dim,
                "cache_hit": bool(cache_hit),
                "model": manifest.key if manifest else None,
            },
            execution_ms=None,
        )

    def verify(self, result: UnitResult, assignment: dict) -> tuple[bool, str | None]:
        if result.status != "completed" or not isinstance(result.value, dict):
            return False, result.error or "expected dim+vectors payload"
        dim = (assignment.get("params") or {}).get("dim", DEFAULT_DIM)
        start, end = assignment["range_start"], assignment["range_end"]
        probe = corpus_text(start)  # re-derive one document locally
        expected_first = HashingEmbedder(dim=dim).embed_documents([probe])[0]
        if result.value.get("vectors", [None])[0] != expected_first:
            return False, "first vector does not match local re-derivation"
        if len(result.value.get("vectors", [])) != end - start + 1:
            return False, "vector count does not match batch size"
        return True, None
