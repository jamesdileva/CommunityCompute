"""Sprint 30: worker refuses assignments whose workload definition is wrong.

A worker re-derives its own local definition for catalog workloads and fails
closed on a version mismatch or a bad/missing definition signature — a
coordinator sending a divergent contract never executes it.
"""

from worker.execution.hello_compute import HelloComputeExecutor
from worker.execution.registry import run_unit

from packages.protocol.signing import DEV_SIGNING_KEY, sign_manifest
from packages.protocol.workloads import attach_signed_definition

SEALED = {
    "protocol_version": "0.1.0-sprint6",
    "work_unit_id": "u1",
    "job_id": "j1",
    "workload_type": "hello_compute",
    "range_start": 1,
    "range_end": 10,
    "params": {"op": "sum"},
}


def sealed(assignment: dict | None = None) -> dict:
    base = dict(SEALED if assignment is None else assignment)
    base["manifest_signature"] = sign_manifest(base, DEV_SIGNING_KEY)
    return attach_signed_definition(base, DEV_SIGNING_KEY)


def _counting_executor(calls: list[str]) -> HelloComputeExecutor:
    class Counting(HelloComputeExecutor):
        def execute(self, assignment):
            calls.append("ran")
            return super().execute(assignment)

    return Counting()


def _run_guarded(assignment: dict, calls: list[str]):
    import worker.execution.registry as registry_mod

    original = registry_mod._EXECUTORS["hello_compute"]
    registry_mod._EXECUTORS["hello_compute"] = _counting_executor(calls)
    try:
        return run_unit(assignment)
    finally:
        registry_mod._EXECUTORS["hello_compute"] = original


def test_valid_signed_definition_executes():
    calls: list[str] = []
    result = _run_guarded(sealed(), calls)
    assert result.status == "completed"
    assert calls == ["ran"]


def test_version_mismatch_refused_without_executing():
    calls: list[str] = []
    assignment = sealed()
    assignment["workload_version"] = "999"
    result = _run_guarded(assignment, calls)
    assert result.status == "failed"
    assert "version mismatch" in result.error
    assert calls == []


def test_missing_definition_signature_refused():
    calls: list[str] = []
    assignment = sealed()
    assignment.pop("workload_signature", None)
    result = _run_guarded(assignment, calls)
    assert result.status == "failed"
    assert "definition signature" in result.error
    assert calls == []


def test_tampered_definition_signature_refused():
    calls: list[str] = []
    assignment = sealed()
    assignment["workload_signature"] = "deadbeef"
    result = _run_guarded(assignment, calls)
    assert result.status == "failed"
    assert "definition signature" in result.error
    assert calls == []


def test_non_catalog_type_falls_through_to_allowlist():
    """Custom (non-catalog) executors aren't definition-gated — only allowlisted."""
    import worker.execution.registry as registry_mod
    from worker.execution.executor import UnitResult, WorkloadExecutor

    class Custom(WorkloadExecutor):
        workload_type = "custom_test"

        def execute(self, assignment):
            return UnitResult(status="completed", value=1)

    assignment = sealed()
    assignment["workload_type"] = "custom_test"
    assignment["manifest_signature"] = sign_manifest(assignment, DEV_SIGNING_KEY)
    original = registry_mod._EXECUTORS.get("custom_test")
    registry_mod._EXECUTORS["custom_test"] = Custom()
    try:
        result = run_unit(assignment)
    finally:
        if original is None:
            registry_mod._EXECUTORS.pop("custom_test", None)
        else:
            registry_mod._EXECUTORS["custom_test"] = original
    assert result.status == "completed"
