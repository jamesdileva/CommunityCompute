"""Sandbox primitives (Sprint 22): low-integrity token + limited Job Object.

Each mechanism is a real kernel boundary, enforced by the OS — not
convention:

- **Low mandatory integrity token** (S-1-16-4096/Low): the sandboxed child
  cannot *write* to normal (Medium-integrity) objects — worker files, user
  documents, and the coordinator DB are write-protected against it. Objects
  labeled Low (our granted work dir) remain writable.
- **Job Object with limits**: hard memory cap, process-count cap (kills
  fork bombs), and KILL_ON_JOB_CLOSE (no orphans when the parent dies).
- **Suspended-start assign**: the child is created suspended and assigned
  to the job *before* it runs, so it can never escape the job.

Honest limits, deliberately documented:
- *Read* denial of Medium objects is NOT enforced (that needs AppContainer,
  whose profile API is absent from this Windows SKU — see worklog). A low
  process can still read files; it cannot corrupt them.
- Network isolation is NOT provided here either (no capability token).
  Sprint 21's static import scan + audit logging remains that control until
  a container/AppContainer path exists.

All of this is stdlib ctypes; no new dependencies.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import ctypes
from ctypes import wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

# Explicit signatures for calls where ctypes' default int passing truncates
# 64-bit handles (e.g. the -1 pseudo-handle from GetCurrentProcess → err 6).
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.CreateJobObjectW.restype = wintypes.HANDLE
advapi32.OpenProcessToken.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)
]
advapi32.DuplicateTokenEx.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
    wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE),
]
advapi32.SetTokenInformation.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD
]
advapi32.AllocateAndInitializeSid.argtypes = [wintypes.LPVOID] + [wintypes.DWORD] * 8 + [
    ctypes.POINTER(ctypes.c_void_p)
]
# Job object calls live in kernel32, not advapi32.
kernel32.SetInformationJobObject.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD
]
kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
kernel32.CreateProcessW.restype = wintypes.BOOL

TOKEN_ALL_ACCESS = 0xF01FF
SecurityImpersonation = 2
TokenPrimary = 1
TokenIntegrityLevel = 25  # TOKEN_INFORMATION_CLASS

# Job Object limit flags.
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x00000400

# Process-creation flags used to dodge the job's escape before assignment.
CREATE_SUSPENDED = 0x00000004
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
CREATE_UNICODE_ENVIRONMENT = 0x00000400

SECURITY_MANDATORY_LOW_RID = 0x1000
SECURITY_MANDATORY_LABEL_AUTHORITY = 16  # identifier authority byte 6 value


class SandboxUnavailable(RuntimeError):
    """Raised when the OS primitives needed for sandboxing are absent."""


def create_limited_job(memory_bytes: int | None, max_processes: int | None
                       ) -> wintypes.HANDLE:
    """Job object with memory/process caps + kill-on-close.

    Caps that don't apply are simply left off; KILL_ON_JOB_CLOSE always is.
    """
    info = _EXTENDED_LIMIT_INFORMATION()
    flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION
    if memory_bytes:
        flags |= JOB_OBJECT_LIMIT_PROCESS_MEMORY
        info.ProcessMemoryLimit = memory_bytes
    if max_processes:
        flags |= JOB_OBJECT_LIMIT_ACTIVE_PROCESS
        info.BasicLimitInformation.ActiveProcessLimit = max_processes
    info.BasicLimitInformation.LimitFlags = flags

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise SandboxUnavailable(f"CreateJobObjectW failed: {ctypes.get_last_error()}")
    ok = kernel32.SetInformationJobObject(
        job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS, ctypes.byref(info),
        ctypes.sizeof(info),
    )
    if not ok:
        _close_handle(job)
        raise SandboxUnavailable(
            f"SetInformationJobObject failed: {ctypes.get_last_error()}"
        )
    return job


def low_integrity_token() -> wintypes.HANDLE:
    """Duplicated current token whose mandatory integrity is Low (S-1-16-4096).

    The kernel wants a TOKEN_MANDATORY_LABEL = {SID_AND_ATTRIBUTES{Sid,
    Attributes}} — a SID pointer plus SE_GROUP_INTEGRITY — not raw SID bytes.
    """
    process = kernel32.GetCurrentProcess()
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(process, TOKEN_ALL_ACCESS, ctypes.byref(token)):
        raise SandboxUnavailable(f"OpenProcessToken failed: {ctypes.get_last_error()}")
    try:
        dup = wintypes.HANDLE()
        if not advapi32.DuplicateTokenEx(
            token, TOKEN_ALL_ACCESS, None, SecurityImpersonation, TokenPrimary,
            ctypes.byref(dup),
        ):
            raise SandboxUnavailable(f"DuplicateTokenEx failed: {ctypes.get_last_error()}")
        try:
            label = TOKEN_MANDATORY_LABEL()
            label.Label.Sid = _low_integrity_sid()
            label.Label.Attributes = SE_GROUP_INTEGRITY
            ok = advapi32.SetTokenInformation(
                dup, TokenIntegrityLevel, ctypes.byref(label), ctypes.sizeof(label)
            )
            if not ok:
                raise SandboxUnavailable(
                    f"SetTokenInformation(integrity) failed: {ctypes.get_last_error()}"
                )
            return dup
        except Exception:
            _close_handle(dup)
            raise
    finally:
        _close_handle(token)


def grant_write_access(path) -> None:
    """Label a directory Low (S-1-16-4096) so low-integrity children can write it.

    Mandatory-label semantics: writes require caller integrity >= object
    label. Labeling our work dir Low lets the sandbox (Low) write while the
    worker process (Medium) and administrators are unaffected.
    """
    import ctypes
    from ctypes import wintypes

    sid = _low_integrity_sid()
    acl = (ctypes.c_byte * 512)()
    ok = advapi32.InitializeAcl(acl, 512, _ACL_REVISION)
    if not ok:
        raise SandboxUnavailable(f'InitializeAcl failed: {ctypes.get_last_error()}')
    ok = advapi32.AddMandatoryAce(
        ctypes.cast(acl, ctypes.c_void_p), _ACL_REVISION,
        _OBJECT_INHERIT_ACE | _CONTAINER_INHERIT_ACE, _SYSTEM_MANDATORY_LABEL_NO_WRITE_UP,
        sid,
    )
    if not ok:
        raise SandboxUnavailable(f'AddMandatoryAce failed: {ctypes.get_last_error()}')
    ok = advapi32.SetNamedSecurityInfoW(
        str(path), _LABEL_SECURITY_INFORMATION, None, None, None, None,
        ctypes.cast(acl, ctypes.c_void_p),
    )
    if ok != 0:
        raise SandboxUnavailable(f"SetNamedSecurityInfo(label) failed: {ok}")


_ACL_REVISION = 2
_OBJECT_INHERIT_ACE = 0x1
_CONTAINER_INHERIT_ACE = 0x2
_SYSTEM_MANDATORY_LABEL_NO_WRITE_UP = 0x1
_LABEL_SECURITY_INFORMATION = 0x00000010


def assign_process_to_job(job: wintypes.HANDLE, process: wintypes.HANDLE) -> None:
    """Attach the already-created (suspended) child to the job object."""
    if not kernel32.AssignProcessToJobObject(job, process):
        raise SandboxUnavailable(
            f"AssignProcessToJobObject failed: {ctypes.get_last_error()}"
        )


def terminate_and_close(job: wintypes.HANDLE) -> None:
    """Kill every process in the job, then release the handle."""
    if job:
        kernel32.TerminateJobObject(job, 1)
        _close_handle(job)


def available() -> bool:
    """True when the Job Object layer (always-on) can be created.

    The low-integrity filesystem layer is optional: it needs elevation or
    AppContainer, neither of which a dev shell has. integrity_available()
    reports that half separately so the sandbox can degrade loudly instead
    of pretending it has a boundary it does not.
    """
    if os.name != "nt":
        return False
    try:
        job = create_limited_job(64 * 1024 * 1024, 1)
    except (SandboxUnavailable, OSError):
        return False
    terminate_and_close(job)
    return True


def integrity_available() -> bool:
    """True when low-integrity tokens can be created (elevation/AppContainer)."""
    if os.name != "nt":
        return False
    try:
        low_integrity_token()
    except (SandboxUnavailable, OSError):
        return False
    return True


# ---- process creation ------------------------------------------------------
def create_suspended_as_user(
    cmdline: str,
    cwd: str,
    env: dict[str, str] | None,
    stdin=None,
    stdout=None,
    stderr=None,
) -> tuple[wintypes.HANDLE, wintypes.HANDLE]:
    """Create a suspended child under the given handles; returns
    (process_handle, thread_handle). The caller assigns the job before resume."""
    from worker.sandbox.launch import create_suspended_process

    return create_suspended_process(cmdline, cwd, env, stdin, stdout, stderr)


# ---- raw helpers ------------------------------------------------------------

SE_GROUP_INTEGRITY = 0x000000C0


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class _TOKEN_MANDATORY_LABEL(ctypes.Structure):
    _fields_ = [("Label", _SID_AND_ATTRIBUTES)]


TOKEN_MANDATORY_LABEL = _TOKEN_MANDATORY_LABEL



class _STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_byte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class _BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _low_integrity_sid() -> ctypes.c_void_p:
    """PSID for S-1-16-4096 (Low) via AllocateAndInitializeSid."""
    authority = (ctypes.c_byte * 6)(*([0] * 5 + [SECURITY_MANDATORY_LABEL_AUTHORITY]))
    sid = ctypes.c_void_p()
    ok = advapi32.AllocateAndInitializeSid(
        ctypes.byref(authority), 1, SECURITY_MANDATORY_LOW_RID, 0, 0, 0, 0, 0, 0,
        ctypes.byref(sid),
    )
    if not ok:
        raise SandboxUnavailable(f"AllocateAndInitializeSid failed: {ctypes.get_last_error()}")
    return sid  # leaked on purpose: short-lived processes, prototype simplicity


def _close_handle(handle: wintypes.HANDLE | None) -> None:
    if handle:
        kernel32.CloseHandle(handle)
