"""Sprint 6: executor validation + deterministic known-answers (worker side)."""

import hashlib

import pytest

from worker.execution.hello_compute import UnitResult, compute, execute_unit, output_hash

GOOD_ASSIGNMENT = {
    "protocol_version": "0.1.0-sprint6",
    "work_unit_id": "u1",
    "job_id": "j1",
    "workload_type": "hello_compute",
    "range_start": 1,
    "range_end": 100,
    "params": {"op": "sum"},
}


def test_sum_known_answer():
    assert compute("sum", 1, 100) == 5050
    assert compute("sum", 901, 1000) == (901 + 1000) * 100 // 2
    assert compute("sum", 5, 5) == 5


def test_hash_matches_coordinator_formula():
    # coordinator-side identical: sha256(f"{start}:{end}")
    assert compute("hash", 1, 100) == hashlib.sha256(b"1:100").hexdigest()
    assert output_hash("sum", 5050) == hashlib.sha256(b"sum:5050").hexdigest()


def test_unknown_op_raises():
    with pytest.raises(ValueError):
        compute("bogus", 1, 10)


def test_execute_completes_with_metrics():
    result = execute_unit(GOOD_ASSIGNMENT)
    assert isinstance(result, UnitResult)
    assert result.status == "completed"
    assert result.value == 5050
    assert result.output_hash == output_hash("sum", 5050)
    assert result.execution_ms is not None and result.execution_ms >= 0


def test_rejects_unknown_workload_type():
    bad = {**GOOD_ASSIGNMENT, "workload_type": "totally_unknown"}
    result = execute_unit(bad)
    assert result.status == "failed"
    assert "no executor" in result.error


def test_rejects_old_protocol_version():
    bad = {**GOOD_ASSIGNMENT, "protocol_version": "0.0.1-old"}
    result = execute_unit(bad)
    assert result.status == "failed"
    assert "protocol" in result.error


def test_rejects_insane_range():
    bad = {**GOOD_ASSIGNMENT, "range_start": 100, "range_end": 1}
    assert execute_unit(bad).status == "failed"
    bad2 = {**GOOD_ASSIGNMENT, "range_start": "one", "range_end": 100}
    assert execute_unit(bad2).status == "failed"


def test_rejects_unsupported_op():
    bad = {**GOOD_ASSIGNMENT, "params": {"op": "train_gpt"}}
    result = execute_unit(bad)
    assert result.status == "failed"
    assert "op" in result.error
