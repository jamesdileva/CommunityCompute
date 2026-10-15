"""Login auto-start via the per-user Registry Run key (Sprint 24).

HKCU (not HKLM): no elevation needed, per-contributor scope — exactly the
prototype's trust posture. The value points at the running executable
(PyInstaller build) or falls back to `python <repo>/main.py` in dev.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "CommunityComputeWorker"


def _open_run_key(write: bool = False):
    import winreg

    access = winreg.KEY_SET_VALUE if write else winreg.KEY_READ
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, access)


def executable_command() -> str:
    """What auto-start should launch: the frozen exe, else the dev entrypoint."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --loop'
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "apps" / "worker" / "worker" / "main.py"
    return f'"{sys.executable}" "{script}" --loop'


def install(command: str | None = None) -> str:
    """Write the Run value. Returns the key path written (for logs/tests)."""
    import winreg

    with _open_run_key(write=True) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command or executable_command())
    return f"HKCU\\{RUN_KEY}\\{VALUE_NAME}"


def remove() -> bool:
    """Delete the Run value. True when something was removed."""
    import winreg

    try:
        with _open_run_key(write=True) as key:
            winreg.DeleteValue(key, VALUE_NAME)
        return True
    except FileNotFoundError:
        return False


def is_installed() -> str | None:
    """The installed command, or None."""
    import winreg

    try:
        with _open_run_key() as key:
            value, _kind = winreg.QueryValueEx(key, VALUE_NAME)
            return str(value)
    except FileNotFoundError:
        return None


def data_dir() -> Path:
    """Per-machine worker data (id, policy, credential, models, logs)."""
    override = os.environ.get("WORKER_DATA_DIR")
    if override:
        return Path(override)
    appdata = os.environ.get("LOCALAPPDATA")
    if appdata:
        return Path(appdata) / "CommunityCompute"
    return Path.home() / ".communitycompute"
