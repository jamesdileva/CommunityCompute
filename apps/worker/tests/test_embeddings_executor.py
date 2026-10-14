"""Sprint 14: embedder adapter + embeddings executor (worker side)."""

from worker.execution.embeddings.embedder import (
    HashingEmbedder,
    corpus_text,
    default_embedder,
)
from worker.execution.embeddings.executor import EmbeddingsExecutor
from worker.execution.registry import executor_for, run_unit, supported_runtimes
from packages.protocol.signing import DEV_SIGNING_KEY, sign_manifest

ASSIGN = {
    "protocol_version": "0.1.0-sprint6",
    "work_unit_id": "u1",
    "job_id": "j1",
    "workload_type": "embeddings",
    "range_start": 1,
    "range_end": 10,
    "params": {"dim": 64},
}


def signed(assignment: dict) -> dict:
    """Attach a valid coordinator seal (Sprint 21: run_unit verifies it)."""
    return {**assignment, "manifest_signature": sign_manifest(assignment, DEV_SIGNING_KEY)}


def test_corpus_is_deterministic():
    assert corpus_text(1) == corpus_text(1)
    assert corpus_text(1) != corpus_text(2)


def test_embedder_deterministic_and_normalized():
    embedder = HashingEmbedder(dim=64)
    v1 = embedder.embed_documents([corpus_text(1)])[0]
    v2 = embedder.embed_documents([corpus_text(1)])[0]
    assert v1 == v2  # deterministic (verification depends on it)
    assert len(v1) == 64
    assert abs(sum(x * x for x in v1) - 1.0) < 1e-4  # L2-normalized


def test_different_docs_different_vectors():
    embedder = HashingEmbedder(dim=128)
    a, b = embedder.embed_documents([corpus_text(1), corpus_text(2)])
    assert a != b


def test_empty_text_zero_vector():
    embedder = HashingEmbedder(dim=32)
    assert embedder.embed_documents([""])[0] == [0.0] * 32


def test_bad_dim_rejected():
    try:
        HashingEmbedder(dim=0)
    except ValueError:
        pass
    else:
        raise AssertionError("dim=0 must raise")


def test_default_embedder():
    assert isinstance(default_embedder(), HashingEmbedder)
    assert default_embedder(32).dim == 32


def test_executor_batch_shape():
    result = run_unit(signed(ASSIGN))
    assert result.status == "completed"
    assert result.value["dim"] == 64
    assert len(result.value["vectors"]) == 10
    assert all(len(v) == 64 for v in result.value["vectors"])
    assert result.metrics["docs"] == 10
    assert result.execution_ms is not None and result.execution_ms >= 0


def test_executor_rejects_bad_dim():
    r = run_unit(signed({**ASSIGN, "params": {"dim": -1}}))
    assert r.status == "failed" and "invalid dim" in r.error


def test_executor_verify_catches_tampering():
    class Tamper(EmbeddingsExecutor):
        def execute(self, assignment):
            result = super().execute(assignment)
            result.value = {"dim": result.value["dim"],
                            "vectors": [[9.0] * len(result.value["vectors"][0])]
                                         + result.value["vectors"][1:]}
            return result

    r = Tamper().run(ASSIGN)
    assert r.status == "failed" and "re-derivation" in r.error


def test_registry_knows_embeddings():
    assert executor_for("embeddings") is not None
    assert "embeddings" in supported_runtimes()


def test_dim_matches_coordinator_reference():
    """Both sides must derive identical vectors (coordinator verifies exactly)."""
    import importlib.util
    from pathlib import Path

    ref_path = Path(__file__).resolve().parents[3] / (
        "apps/coordinator/app/services/workloads/embeddings.py"
    )
    spec = importlib.util.spec_from_file_location("ref_embeddings", ref_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected = module.compute_batch(1, 3, dim=32)
    got = run_unit(signed({**ASSIGN, "range_start": 1, "range_end": 3, "params": {"dim": 32}}))
    assert got.value == expected
