"""Sprint 13: adapter interface, lifecycle ordering, multi-workload registry."""

import worker.main as main_mod
from worker.execution.executor import ExecutorMetadata, UnitResult, WorkloadExecutor
from worker.execution.hello_compute import HelloComputeExecutor, compute, output_hash
from worker.execution.registry import (
    executor_for,
    list_executors,
    run_unit,
    supported_runtimes,
)
from worker.execution.stats_range import StatsRangeExecutor

GOOD = {
    "protocol_version": "0.1.0-sprint6",
    "work_unit_id": "u1",
    "job_id": "j1",
    "workload_type": "hello_compute",
    "range_start": 1,
    "range_end": 100,
    "params": {"op": "sum"},
}


# ---- interface contract ----------------------------------------------------


def test_metadata_declares_requirements():
    hello = HelloComputeExecutor().metadata
    stats = StatsRangeExecutor().metadata
    assert hello.workload_type == "hello_compute"
    assert stats.workload_type == "stats_range"
    assert stats.requirements == {"cpu_cores": 1}  # declarative, scheduler-visible


def test_capabilities_fit_check():
    executor = StatsRangeExecutor()
    # meets declared cpu requirement
    ok, _ = executor.can_execute(
        {**GOOD, "workload_type": "stats_range"},
        {"cpu": {"logical_cores": 4}},
    )
    assert ok is True
    # gpu-declaring executor rejects a GPU-less machine


class _GpuExecutor(WorkloadExecutor):
    workload_type = "fake_gpu"

    def execute(self, assignment: dict) -> UnitResult:
        return UnitResult(status="completed", value="x")

    @property
    def metadata(self):
        from worker.execution.executor import ExecutorMetadata

        return ExecutorMetadata(workload_type="fake_gpu",
                                requirements={"gpu": True, "gpu_vendor": "nvidia"})


def test_declared_gpu_requirement_enforced():
    executor = _GpuExecutor()
    assign = {**GOOD, "workload_type": "fake_gpu"}
    ok, reason = executor.can_execute(assign, {"gpus": []})
    assert ok is False and "gpu" in reason
    ok, _ = executor.can_execute(
        assign, {"gpus": [{"vendor": "nvidia", "vram_mb": 8192}]}
    )
    assert ok is True


# ---- lifecycle --------------------------------------------------------------


def test_lifecycle_runs_all_stages_in_order():
    calls: list[str] = []

    class Instrumented(WorkloadExecutor):
        workload_type = "instrumented"

        def prepare(self, assignment):
            calls.append("prepare")

        def execute(self, assignment):
            calls.append("execute")
            return UnitResult(status="completed", value=1)

        def verify(self, result, assignment):
            calls.append("verify")
            return True, None

        def cleanup(self):
            calls.append("cleanup")

    result = Instrumented().run({**GOOD, "workload_type": "instrumented"})
    assert calls == ["prepare", "execute", "verify", "cleanup"]
    assert result.status == "completed"
    assert result.execution_ms is not None  # runner times execution


def test_lifecycle_maps_stage_failures():
    class BadPrepare(WorkloadExecutor):
        workload_type = "bad_prepare"

        def prepare(self, assignment):
            raise RuntimeError("model missing")

        def execute(self, assignment):
            raise AssertionError("must not run")

    r = BadPrepare().run({**GOOD, "workload_type": "bad_prepare"})
    assert r.status == "failed" and "prepare failed" in r.error

    class BadExecute(WorkloadExecutor):
        workload_type = "bad_execute"

        def execute(self, assignment):
            raise RuntimeError("boom")

    r = BadExecute().run({**GOOD, "workload_type": "bad_execute"})
    assert r.status == "failed" and "execution error" in r.error

    class BadVerify(WorkloadExecutor):
        workload_type = "bad_verify"

        def execute(self, assignment):
            return UnitResult(status="completed", value="wrong")

        def verify(self, result, assignment):
            return False, "worker-side verification failed"

    r = BadVerify().run({**GOOD, "workload_type": "bad_verify"})
    assert r.status == "failed" and r.value is None and "verification failed" in r.error


def test_validation_failure_skips_execution():
    class Counting(WorkloadExecutor):
        workload_type = "counting"

        def execute(self, assignment):
            raise AssertionError("must not run after rejection")

    bad = {**GOOD, "workload_type": "counting", "protocol_version": "0.0.0-old"}
    r = Counting().run(bad)
    assert r.status == "failed" and "protocol" in r.error


def test_cleanup_failure_does_not_break_result():
    class DirtyCleanup(WorkloadExecutor):
        workload_type = "dirty"

        def execute(self, assignment):
            return UnitResult(status="completed", value=5)

        def cleanup(self):
            raise RuntimeError("temp dir locked")

    r = DirtyCleanup().run({**GOOD, "workload_type": "dirty"})
    assert r.status == "completed" and r.value == 5


def test_runner_times_execution():
    r = run_unit(GOOD)
    assert r.status == "completed" and r.value == 5050
    assert r.execution_ms is not None and r.execution_ms >= 0
    assert r.output_hash == output_hash("sum", 5050)


# ---- workload-agnostic pipeline (exit condition, worker side) ---------------


def test_two_workloads_same_path():
    hello = run_unit(GOOD)
    stats = run_unit({**GOOD, "workload_type": "stats_range"})
    assert hello.status == "completed" and hello.value == 5050
    assert stats.status == "completed"
    assert stats.value == {"count": 100, "sum": 5050, "max": 100, "min": 1}


def test_stats_range_local_verify_catches_corruption():
    class CorruptStats(StatsRangeExecutor):
        def execute(self, assignment):
            result = super().execute(assignment)
            result.value = {"count": 99, "sum": 1, "max": 1, "min": 1}
            return result

    r = CorruptStats().run({**GOOD, "workload_type": "stats_range"})
    assert r.status == "failed" and "stats mismatch" in r.error

def test_registry_dispatch_and_miss():
    assert isinstance(executor_for("hello_compute"), HelloComputeExecutor)
    assert isinstance(executor_for("stats_range"), StatsRangeExecutor)
    from worker.execution.embeddings.executor import EmbeddingsExecutor

    assert isinstance(executor_for("embeddings"), EmbeddingsExecutor)
    assert executor_for("nope") is None
    assert sorted(supported_runtimes()) == ["embeddings", "hello_compute", "stats_range"]
    assert len(list_executors()) == 3


def test_unknown_workload_fails_closed():
    r = run_unit({**GOOD, "workload_type": "totally_unknown"})
    assert r.status == "failed" and "no executor" in r.error


def test_stats_and_hello_hash_payloads_are_separate():
    import hashlib

    hello_hash = run_unit({**GOOD, "params": {"op": "hash"}})
    assert hello_hash.value == hashlib.sha256(b"1:100").hexdigest()


def test_work_cycle_uses_registry(monkeypatch):
    """Worker loop path: claim -> run_unit -> submit (Sprint 12 wiring intact)."""
    submitted: list[dict] = []
    monkeypatch.setattr(
        main_mod, "claim_work",
        lambda *a, **k: {**GOOD, "workload_type": "stats_range"},
    )
    monkeypatch.setattr(main_mod, "submit_result",
                        lambda url, unit_id, body, timeout=None, verify=True:
                        submitted.append(body)
                        or {"ok": True})
    main_mod._attempt_work_cycle("http://x", "w1", 5.0, availability=(True, "ok"))
    assert submitted[0]["value"]["sum"] == 5050
