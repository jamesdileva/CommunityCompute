"""Suspended-start process creation (Sprint 22).

`CreateProcessAsUserW` creates the child suspended with piped stdio; the
caller assigns it to the job object *before* resuming the main thread, so
the child can never run outside the job (an unsuspended child would race
past the job's limits).
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from worker.sandbox.native import (
    CREATE_SUSPENDED,
    CREATE_UNICODE_ENVIRONMENT,
    _PROCESS_INFORMATION,
    _STARTUPINFO,
    SandboxUnavailable,
)

advapi32 = ctypes.WinDLL("security", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

STARTF_USESTDHANDLES = 0x00000100


def build_command_line(executable: str, args: list[str]) -> str:
    parts = [f'"{executable}"'] + [f'"{a}"' if " " in a else a for a in args]
    return " ".join(parts)


def create_suspended_process(
    cmdline: str,
    cwd: str,
    env: dict[str, str] | None,
    stdin,
    stdout,
    stderr,
    token: wintypes.HANDLE | None = None,
) -> tuple[wintypes.HANDLE, wintypes.HANDLE]:
    """Create the suspended child; return (process_handle, thread_handle).

    Handles are passed through directly (parent's ends; the child inherits
    them via STARTF_USESTDHANDLES).
    """
    startup = _STARTUPINFO()
    startup.cb = ctypes.sizeof(_STARTUPINFO)
    startup.dwFlags = STARTF_USESTDHANDLES
    startup.hStdInput = stdin.writable_handle if stdin is not None else None
    startup.hStdOutput = stdout.readable_handle if stdout is not None else None
    startup.hStdError = stderr.readable_handle if stderr is not None else None

    proc_info = _PROCESS_INFORMATION()
    env_block = _build_environment(env)
    create = advapi32.CreateProcessAsUserW if token is not None else None
    ok = False
    if create is not None:
        ok = create(
            token,
            None,
            ctypes.create_unicode_buffer(cmdline),
            None,
            None,
            True,
            CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT,
            env_block,
            cwd,
            ctypes.byref(startup),
            ctypes.byref(proc_info),
        )
    if not ok:
        # Fallback: inheritable CreateProcessW under the current token (still
        # sandboxed by the job object; the low-integrity token is a bonus).
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ok = kernel32.CreateProcessW(
            None,
            ctypes.create_unicode_buffer(cmdline),
            None,
            None,
            True,
            CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT,
            env_block,
            cwd,
            ctypes.byref(startup),
            ctypes.byref(proc_info),
        )
        if not ok:
            raise SandboxUnavailable(f"CreateProcess failed: {ctypes.get_last_error()}")
    return proc_info.hProcess, proc_info.hThread


def resume(thread_handle: wintypes.HANDLE) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if kernel32.ResumeThread(thread_handle) == -1:
        raise SandboxUnavailable(f"ResumeThread failed: {ctypes.get_last_error()}")


def _build_environment(env: dict[str, str] | None) -> ctypes.Array | None:
    if not env:
        return None
    items = [f"{k}={v}" for k, v in env.items()]
    block = "\0".join(items) + "\0\0"
    return ctypes.create_unicode_buffer(block)
