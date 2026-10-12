"""Embeddings workload (Sprint 14): batch embedding over deterministic corpus ranges."""

from worker.execution.embeddings.embedder import HashingEmbedder, corpus_text
from worker.execution.executor import ExecutorMetadata, UnitResult, WorkloadExecutor

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

    def execute(self, assignment: dict) -> UnitResult:
        dim = (assignment.get("params") or {}).get("dim", DEFAULT_DIM)
        if not isinstance(dim, int) or dim <= 0:
            return UnitResult(status="failed", error=f"invalid dim {dim!r}")
        embedder = HashingEmbedder(dim=dim)
        start, end = assignment["range_start"], assignment["range_end"]
        texts = [corpus_text(i) for i in range(start, end + 1)]
        vectors = embedder.embed_documents(texts)
        return UnitResult(
            status="completed",
            value={"dim": dim, "vectors": vectors},
            metrics={"docs": len(texts), "dim": dim},
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
