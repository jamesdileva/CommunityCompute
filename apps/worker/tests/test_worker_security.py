"""Sprint 21: worker-side boundary — seals, timeouts, temp dirs, static bans."""

import ast
import time
from pathlib import Path

import pytest

from packages.protocol.signing import DEV_SIGNING_KEY, sign_manifest
from worker.execution.hello_compute import HelloComputeExecutor
from worker.execution.registry import DEFAULT_UNIT_TIME_LIMIT, run_unit
from worker.security.paths import PathEscapeError, safe_join

SEALED = {
    "protocol_version": "0.1.0-sprint6",
    "work_unit_id": "u1",
    "job_id": "j1",
    "workload_type": "hello_compute",
    "range_start": 1,
    "range_end": 10,
    "params": {"op": "sum"},
}


def sealed(assignment: dict | None = None, key: str = DEV_SIGNING_KEY) -> dict:
    base = dict(SEALED if assignment is None else assignment)
    base["manifest_signature"] = sign_manifest(base, key)
    return base


def test_missing_signature_refused_without_executing():
    calls: list[str] = []

    class Counting(HelloComputeExecutor):
        def execute(self, assignment):
            calls.append("ran")
            return super().execute(assignment)

    import worker.execution.registry as registry_mod

    original = registry_mod._EXECUTORS["hello_compute"]
    registry_mod._EXECUTORS["hello_compute"] = Counting()
    try:
        result = run_unit(dict(SEALED))  # no seal at all
    finally:
        registry_mod._EXECUTORS["hello_compute"] = original
    assert result.status == "failed"
    assert "signature" in result.error
    assert calls == []  # executor never ran


def test_tampered_assignment_refused():
    good = sealed()
    tampered = {**good, "range_end": 5000}  # same seal, different inputs
    result = run_unit(tampered)
    assert result.status == "failed"
    assert "signature" in result.error


def test_wrong_key_refused(monkeypatch):
    monkeypatch.setenv("WORKLOAD_SIGNING_KEY", "attacker-key")
    result = run_unit(sealed())  # sealed with the dev key, verified against attacker key
    assert result.status == "failed"
    assert "signature" in result.error


def test_valid_seal_executes():
    result = run_unit(sealed())
    assert result.status == "completed" and result.value == 55


def test_execution_timeout_fails_the_unit():
    class Slow(HelloComputeExecutor):
        workload_type = "slow_test"

        def execute(self, assignment):
            time.sleep(5.0)
            return super().execute(assignment)

    import worker.execution.registry as registry_mod

    registry_mod._EXECUTORS["slow_test"] = Slow()
    try:
        assignment = sealed({**SEALED, "workload_type": "slow_test"})
        started = time.monotonic()
        result = run_unit(assignment, time_limit=0.2)
        elapsed = time.monotonic() - started
    finally:
        del registry_mod._EXECUTORS["slow_test"]
    assert result.status == "failed"
    assert "time limit exceeded" in result.error
    assert elapsed < 4.0  # returned promptly; the abandoned thread is not joined


def test_missing_work_root_fails_unit_not_worker(tmp_path):
    """run_unit's never-raises contract holds for environment failures too."""
    missing = tmp_path / "no-such-dir"
    result = run_unit(sealed(), work_root=str(missing))
    assert result.status == "failed"
    assert "work directory unavailable" in result.error


def test_temp_work_dir_created_and_cleaned(tmp_path):
    seen: list[str] = []

    class Snooping(HelloComputeExecutor):
        workload_type = "snoop_test"

        def execute(self, assignment):
            seen.append(assignment.get("work_dir", ""))
            assert Path(assignment["work_dir"]).is_dir()
            return super().execute({**assignment, "workload_type": "hello_compute"})

    import worker.execution.registry as registry_mod

    registry_mod._EXECUTORS["snoop_test"] = Snooping()
    try:
        assignment = sealed({**SEALED, "workload_type": "snoop_test"})
        result = run_unit(assignment, work_root=str(tmp_path))
    finally:
        del registry_mod._EXECUTORS["snoop_test"]
    assert result.status == "completed"
    assert seen and not Path(seen[0]).exists()  # cleaned after the run
    assert not any(tmp_path.iterdir())  # nothing left behind


def test_safe_join_allows_inside(tmp_path):
    base = tmp_path / "work-xyz"
    base.mkdir()
    assert safe_join(base, "out.json") == base / "out.json"
    assert safe_join(base, "sub", "x.bin") == base / "sub" / "x.bin"
    assert safe_join(base, "sub", "..", "ok.json") == base / "ok.json"


def test_safe_join_refuses_escape(tmp_path):
    base = (tmp_path / "work-xyz").resolve()
    with pytest.raises(PathEscapeError):
        safe_join(base, "..", "etc", "passwd")
    with pytest.raises(PathEscapeError):
        safe_join(base, "../../etc/passwd")


def test_workload_code_has_no_network_or_process_imports():
    """Static boundary (Sprint 21): workload modules import no socket/httpx/
    urllib/subprocess — platform code (capabilities/monitoring) is allowed
    those; workload code is not. The OS-level half lands in Sprint 22."""
    banned = {"socket", "httpx", "urllib", "urllib.request", "urllib.parse",
              "subprocess", "multiprocessing", "os.system", "http.client"}
    root = Path(__file__).resolve().parents[1] / "worker" / "execution"
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue  # syntax is the syntax-checker's problem, not ours
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        hit = imported & banned
        if hit:
            offenders.append(f"{path.name}: {sorted(hit)}")
    assert offenders == [], f"workload modules must not import {offenders}"


def test_default_time_limit_is_sane():
    assert DEFAULT_UNIT_TIME_LIMIT >= 60.0
