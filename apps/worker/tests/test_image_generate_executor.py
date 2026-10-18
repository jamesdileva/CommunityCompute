"""Sprint 33: the image_generate (GPU-gated) worker executor.

Verifies the executor is registered, produces the deterministic tile checksum
the coordinator expects, self-verifies before submission, and runs through the
signed-definition gate like every catalog workload.
"""

from worker.execution.image_generate import ImageGenerateExecutor, compute, tile
from worker.execution.registry import run_unit, supported_runtimes

from packages.protocol.signing import DEV_SIGNING_KEY, sign_manifest
from packages.protocol.workloads import attach_signed_definition


def _sealed(assignment: dict) -> dict:
    base = dict(assignment)
    base["manifest_signature"] = sign_manifest(base, DEV_SIGNING_KEY)
    return attach_signed_definition(base, DEV_SIGNING_KEY)


def _assignment(params: dict | None = None) -> dict:
    return {
        "protocol_version": "0.1.0-sprint6",
        "work_unit_id": "u1",
        "job_id": "j1",
        "workload_type": "image_generate",
        "range_start": 1,
        "range_end": 4,
        "params": params or {"size": 8},
    }


def test_executor_registered():
    assert "image_generate" in supported_runtimes()


def test_compute_is_deterministic_and_sized():
    value = compute(1, 4, size=8, seed="cc")
    assert value == compute(1, 4, size=8, seed="cc")
    assert value["tiles"] == 4
    assert value["size"] == 8
    assert value["checksum"] == compute(1, 4, 8, "cc")["checksum"]
    # Different seed -> different tiles -> different checksum.
    assert tile("cc", 1, 8) != tile("other", 1, 8)


def test_execute_then_verify_accepts():
    executor = ImageGenerateExecutor()
    assignment = _assignment()
    result = executor.execute(assignment)
    assert result.status == "completed"
    ok, reason = executor.verify(result, assignment)
    assert ok, reason


def test_verify_rejects_tampered_checksum():
    executor = ImageGenerateExecutor()
    assignment = _assignment()
    result = executor.execute(assignment)
    result.value["checksum"] = "deadbeef"
    ok, reason = executor.verify(result, assignment)
    assert not ok
    assert "mismatch" in reason


def test_run_unit_executes_signed_assignment():
    result = run_unit(_sealed(_assignment()))
    assert result.status == "completed", result.error
    assert result.value == compute(1, 4, 8, "cc")
