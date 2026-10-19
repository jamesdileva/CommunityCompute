"""Sprint 24: setup wizard, autostart, update check, log file."""

import json
import sys
from pathlib import Path

import pytest

from worker.autostart import (
    VALUE_NAME,
    data_dir,
    executable_command,
    install,
    is_installed,
    remove,
)
from worker.setup_wizard import run_setup
from worker.tray import dashboard_url, menu_state, status_tooltip
from worker.tray import TrayState


def _answers(values: list[str]):
    it = iter(values)

    def ask(prompt: str = "") -> str:
        return next(it)

    return ask


def _gpu_metered() -> dict:
    """Deterministic probe: GPU metrics readable, so GPU limits are offered."""
    return {"utilization_gpu": 4.0, "temperature_gpu": 38.0, "memory_used_mb": 512}


def test_wizard_defaults(tmp_path):
    out: list[str] = []
    configured = run_setup(
        tmp_path / ".worker_id",
        input_fn=_answers(["", "", "", "", "", "", "", "", "", ""]),
        print_fn=out.append,
        gpu_probe=_gpu_metered,
    )
    assert configured["coordinator_url"] == "http://127.0.0.1:8000"
    assert configured["enrollment_token"] is None
    assert configured["idle_only"] is True
    assert configured["max_cpu_percent"] == 80.0
    assert configured["max_gpu_percent"] == 80.0
    assert configured["temperature_ceiling_c"] is None
    assert configured["battery_policy"] == "allow"
    assert configured["bandwidth_mbps"] is None
    assert configured["autostart"] is False
    policy = json.loads((tmp_path / "policy.json").read_text(encoding="utf-8"))
    assert policy["idle_only"] is True
    assert any("worker --coordinator-url" in line for line in out)
    assert any("docs/privacy.md" in line for line in out)
    assert any("Hardware scan" in line for line in out)
    assert any("Contribution class:" in line for line in out)


def test_wizard_custom_answers(tmp_path):
    configured = run_setup(
        tmp_path / ".worker_id",
        input_fn=_answers(["http://pc:8000", "tok-123", "y", "50", "60",
                           "70", "plugged_only", "9-17", "10", "n"]),
        print_fn=lambda _line: None,
        gpu_probe=_gpu_metered,
    )
    assert configured["coordinator_url"] == "http://pc:8000"
    assert configured["enrollment_token"] == "tok-123"
    assert configured["max_cpu_percent"] == 50.0
    assert configured["max_gpu_percent"] == 60.0
    assert configured["temperature_ceiling_c"] == 70.0
    assert configured["battery_policy"] == "plugged_only"
    assert configured["bandwidth_mbps"] == 10.0
    saved = json.loads((tmp_path / "policy.json").read_text(encoding="utf-8"))
    assert saved["allowed_hours"] == {"start_hour": 9, "end_hour": 17, "days": []}


def test_wizard_bad_cpu_falls_back_to_default(tmp_path):
    configured = run_setup(
        tmp_path / ".worker_id",
        input_fn=_answers(["", "", "", "lots", "", "", "", "", "", ""]),
        print_fn=lambda _line: None,
        gpu_probe=_gpu_metered,
    )
    assert configured["max_cpu_percent"] == 80.0


@pytest.mark.skipif(sys.platform != "win32", reason="HKCU Run key is Windows-only")
def test_autostart_roundtrip_on_temp_key(monkeypatch, tmp_path):
    """Install/remove against the real registry shape (cleaned up after)."""
    import winreg

    # Redirect to a scratch value name so the test never touches a real entry.
    monkeypatch.setattr("worker.autostart.VALUE_NAME", "CommunityComputeWorkerTest")
    try:
        where = install("C:\\fake\\worker.exe --loop")
        assert "CommunityComputeWorkerTest" in where
        assert is_installed() == "C:\\fake\\worker.exe --loop"
        assert remove() is True
        assert is_installed() is None
        assert remove() is False
    finally:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE,
            ) as key:
                winreg.DeleteValue(key, "CommunityComputeWorkerTest")
        except FileNotFoundError:
            pass
        assert VALUE_NAME == "CommunityComputeWorker"


def test_executable_command_shapes():
    cmd = executable_command()
    assert "--loop" in cmd
    assert "main.py" in cmd or cmd.endswith(".exe --loop\"" ) or cmd.endswith(".exe --loop")


def test_data_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKER_DATA_DIR", str(tmp_path / "data"))
    assert data_dir() == tmp_path / "data"


def test_tray_status_text():
    state = TrayState(worker_id="abcdef123456", coordinator_url="http://x:8000",
                      status="online", paused=False, units_completed=3)
    assert status_tooltip(state) == "CommunityCompute online (abcdef12) — 3 units done"
    paused = TrayState(worker_id="abcdef123456", coordinator_url="http://x:8000",
                       status="paused", paused=True)
    assert "paused by you" in status_tooltip(paused)
    fresh = TrayState(worker_id="abcdef123456", coordinator_url="http://x:8000",
                      status="online", paused=False)
    assert status_tooltip(fresh) == "CommunityCompute online (abcdef12)"


def test_tray_menu_state():
    assert menu_state(False) == {"pause_label": "Pause contributing",
                                 "pause_checked": False}
    assert menu_state(True) == {"pause_label": "Resume contributing",
                                "pause_checked": True}


def test_dashboard_url():
    assert dashboard_url("http://127.0.0.1:8000") == "http://127.0.0.1:5173"


def test_check_update_current(monkeypatch):
    import httpx

    import worker.main as main_mod

    def fake_get(url, timeout=None, verify=True):
        import worker as worker_pkg

        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"version": worker_pkg.__version__},
                              request=request)

    monkeypatch.setattr(httpx, "get", fake_get)
    assert main_mod._check_update("http://x:8000", 5.0) == 0


def test_check_update_available(monkeypatch, capsys):
    import httpx

    import worker.main as main_mod

    def fake_get(url, timeout=None, verify=True):
        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"version": "9.9.9-future"}, request=request)

    monkeypatch.setattr(httpx, "get", fake_get)
    assert main_mod._check_update("http://x:8000", 5.0) == 2
    assert "update exists" in capsys.readouterr().out


def test_check_update_unreachable(monkeypatch):
    import httpx

    import worker.main as main_mod

    def boom(*_a, **_k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "get", boom)
    assert main_mod._check_update("http://x:8000", 5.0) == 1


def test_log_file_writes(tmp_path, monkeypatch):
    import worker.main as main_mod

    log = tmp_path / "worker.log"
    args = main_mod.parse_args(["--log-file", str(log), "--once"])
    assert args.log_file == str(log)
    main_mod._enable_file_log(str(log))
    print("hello-log-file-marker", flush=True)
    try:
        assert "hello-log-file-marker" in log.read_text(encoding="utf-8")
    finally:
        import sys as _sys

        # restore real streams for the rest of the session
        _sys.stdout = _sys.stdout._stream if hasattr(_sys.stdout, "_stream") else _sys.stdout
        _sys.stderr = _sys.stderr._stream if hasattr(_sys.stderr, "_stream") else _sys.stderr
