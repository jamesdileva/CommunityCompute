"""Sprint 15: executor prepare() uses the model cache; metrics record cache_hit."""

import os

from worker.execution.embeddings.executor import DEFAULT_DIM, EmbeddingsExecutor
from worker.execution.registry import run_unit
from worker.models.cache import ModelCache, default_cache_dir
from worker.models.manifest import manifest_for

MANIFEST = manifest_for("embeddings")


def _fresh_dir(tmp_path) -> str:
    os.environ["MODEL_CACHE_DIR"] = str(tmp_path)
    return str(tmp_path)


def test_non_model_workload_unaffected(tmp_path):
    _fresh_dir(tmp_path)
    result = run_unit({"protocol_version": "0.1.0-sprint6", "work_unit_id": "u1",
                       "job_id": "j1", "workload_type": "hello_compute",
                       "range_start": 1, "range_end": 10, "params": {"op": "sum"}})
    assert result.status == "completed" and result.value == 55
    assert (result.metrics or {}).get("cache_hit") is None


def test_prepare_fetches_once_then_reports_cache_hit(tmp_path):
    _fresh_dir(tmp_path)
    executor = EmbeddingsExecutor()
    assignment = {"protocol_version": "0.1.0-sprint6", "work_unit_id": "u1",
                  "job_id": "j1", "workload_type": "embeddings",
                  "range_start": 1, "range_end": 3, "params": {"dim": 32}}
    result1 = executor.run(assignment)
    assert result1.status == "completed"
    assert result1.metrics["cache_hit"] is False  # first run fetched

    executor2 = EmbeddingsExecutor()
    result2 = executor2.run(assignment)
    assert result2.metrics["cache_hit"] is True  # cached → no fetch


def test_cache_hit_transition_in_metrics(tmp_path):
    _fresh_dir(tmp_path)
    assignment = {"protocol_version": "0.1.0-sprint6", "work_unit_id": "u1",
                  "job_id": "j1", "workload_type": "embeddings",
                  "range_start": 1, "range_end": 2, "params": {"dim": 16}}
    r1 = run_unit(assignment)
    r2 = run_unit(assignment)
    assert r1.metrics["cache_hit"] is False
    assert r2.metrics["cache_hit"] is True
    assert r1.value == r2.value  # embedding output unchanged


def test_prepare_failure_becomes_failed_unit(tmp_path):
    _fresh_dir(tmp_path)
    # corrupt the expected sha so ensure() raises inside prepare()
    manifest = type(MANIFEST)(**{**MANIFEST.__dict__, "sha256": "0" * 64})
    import worker.execution.embeddings.executor as executor_mod

    original = executor_mod.manifest_for
    executor_mod.manifest_for = lambda _t: manifest
    try:
        result = run_unit({"protocol_version": "0.1.0-sprint6", "work_unit_id": "u1",
                          "job_id": "j1", "workload_type": "embeddings",
                          "range_start": 1, "range_end": 2, "params": {"dim": 16}})
    finally:
        executor_mod.manifest_for = original
    assert result.status == "failed"
    assert "prepare failed" in result.error and "sha256" in result.error


def test_dim_still_configurable_with_cache(tmp_path):
    _fresh_dir(tmp_path)
    result = run_unit({"protocol_version": "0.1.0-sprint6", "work_unit_id": "u1",
                       "job_id": "j1", "workload_type": "embeddings",
                       "range_start": 1, "range_end": 2, "params": {"dim": 8}})
    assert result.status == "completed"
    assert result.value["dim"] == 8
    assert DEFAULT_DIM == 128
    cached = ModelCache(default_cache_dir()).list_cached()
    assert cached == [{"name": "hashing-embedder", "version": "1"}]


def test_non_model_workload_unaffected(tmp_path):
    _fresh_dir(tmp_path)
    result = run_unit({"protocol_version": "0.1.0-sprint6", "work_unit_id": "u1",
                       "job_id": "j1", "workload_type": "hello_compute",
                       "range_start": 1, "range_end": 10, "params": {"op": "sum"}})
    assert result.status == "completed" and result.value == 55
    assert (result.metrics or {}).get("cache_hit") is None
