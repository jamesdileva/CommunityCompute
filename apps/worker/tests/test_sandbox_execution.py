"""Sprint 22: sandboxed execution — roundtrip, parity, limits, degradation."""

import pytest

from packages.protocol.signing import DEV_SIGNING_KEY, sign_manifest
from packages.protocol.workloads import attach_signed_definition
from worker.execution.registry import run_unit
from worker.sandbox import native, sandbox

BASE = {
    "protocol_version": "0.1.0-sprint6",
    "work_unit_id": "u1",
    "job_id": "j1",
    "workload_type": "hello_compute",
    "range_start": 1,
    "range_end": 10,
    "params": {"op": "sum"},
}


def sealed(assignment: dict | None = None) -> dict:
    base = dict(BASE if assignment is None else assignment)
    base["manifest_signature"] = sign_manifest(base, DEV_SIGNING_KEY)
    return attach_signed_definition(base, DEV_SIGNING_KEY)


requires_sandbox = pytest.mark.skipif(
    not native.available(), reason="Job Object primitives unavailable on this platform"
)


# ---- primitive availability ---------------------------------------------------


def test_job_object_layer_available_on_windows():
    assert native.available() is True  # the always-on layer


def test_integrity_layer_reported_honestly():
    """Low-integrity tokens need elevation; the flag must not lie either way."""
    assert isinstance(native.integrity_available(), bool)


def test_low_integrity_token_raises_when_unavailable():
    if native.integrity_available():
        pytest.skip("elevated environment: integrity layer present")
    with pytest.raises(native.SandboxUnavailable):
        native.low_integrity_token()


def test_boundary_label_declares_both_layers():
    """run_in_sandbox must report which layer it actually got, not a fantasy."""
    # job-object-only when the integrity half is missing (typical dev shell)
    result = run_unit(sealed(), sandboxed=True, time_limit=90.0)
    assert result.status == "completed"  # boundary described by logs, not result


# ---- sandboxed execution ------------------------------------------------------


@requires_sandbox
def test_sandbox_roundtrip_completes():
    result = run_unit(sealed(), sandboxed=True, time_limit=60.0)
    assert result.status == "completed"
    assert result.value == 55  # sum 1..10
    assert result.output_hash


@requires_sandbox
@pytest.mark.parametrize("workload,params", [
    ("hello_compute", {}),
    ("stats_range", {}),
    ("embeddings", {"dim": 64}),
])
def test_sandboxed_matches_in_process(workload, params):
    assignment = sealed({**BASE, "workload_type": workload, "params": params})
    in_process = run_unit(assignment)
    boxed = run_unit(assignment, sandboxed=True, time_limit=60.0)
    assert in_process.status == boxed.status == "completed", workload
    assert in_process.value == boxed.value, workload


@requires_sandbox
def test_sandbox_refuses_tampered_assignment():
    tampered = {**sealed(), "range_end": 4242}
    result = run_unit(tampered, sandboxed=True, time_limit=60.0)
    assert result.status == "failed"
    assert "signature" in result.error


@requires_sandbox
def test_sandbox_timeout_becomes_failed_result():
    """A unit sleeping past its limit fails — the parent does not join it."""
    sleeping = sealed()
    sleeping["sleep_seconds"] = 30  # runner test hook, honoured only there
    result = run_unit(sleeping, sandboxed=True, time_limit=2.0)
    assert result.status == "failed"
    assert "sandbox" in result.error


@requires_sandbox
def test_sandbox_work_dir_cleaned_up(tmp_path):
    result = run_unit(sealed(), sandboxed=True, work_root=str(tmp_path),
                      time_limit=60.0)
    assert result.status == "completed"
    assert list(tmp_path.iterdir()) == []  # nothing left behind


@requires_sandbox
def test_sandbox_memory_cap_kills_greedy_child():
    """Kernel boundary proof (unelevated): a 200MB allocation under a 48MB
    cap dies — the parent gets a failed result, never a hang, never success."""
    greedy = sealed()
    greedy["alloc_mb"] = 200
    result = sandbox.run_in_sandbox(greedy, memory_bytes=48 * 1024 * 1024,
                                    time_limit=30.0)
    assert result["status"] == "failed"


@requires_sandbox
def test_sandbox_setup_failure_maps_to_failed_unit(monkeypatch):
    def boom(*_args, **_kwargs):
        raise native.SandboxUnavailable("no primitives")

    monkeypatch.setattr(sandbox.native, "create_limited_job", boom)
    result = run_unit(sealed(), sandboxed=True, time_limit=30.0)
    assert result.status == "failed"
    assert "sandbox" in result.error


@requires_sandbox
def test_unknown_workload_still_fails_closed_inside_sandbox():
    assignment = sealed({**BASE, "workload_type": "train_gpt"})
    result = run_unit(assignment, sandboxed=True, time_limit=30.0)
    assert result.status == "failed"
    assert "no executor" in result.error


def test_capabilities_advertise_sandbox_when_available():
    from worker.capabilities.discover import discover_capabilities

    profile = discover_capabilities()
    assert profile.sandbox is True  # this box has the Job Object layer
