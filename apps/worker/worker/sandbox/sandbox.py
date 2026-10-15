"""Sandboxed execution orchestrator (Sprint 22).

`run_in_sandbox(assignment)` runs one work unit in a child process that is
BOTH low-integrity (cannot write worker/user files) and inside a limited
Job Object (memory cap, process cap, kill-on-close). The child gets exactly
one writable location: its own temporary work directory, labeled Low so the
sandbox can write there and the worker still can.

Pipe discipline: the parent writes one JSON line (the assignment, with its
`work_dir`) to the child's stdin and reads back exactly one JSON line from
its stdout; a crash or timeout becomes a `failed` result payload.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path

from worker.sandbox import native

_REPO_ROOT = Path(__file__).resolve().parents[4]
_APPS_WORKER = Path(__file__).resolve().parents[2]


def run_in_sandbox(
    assignment: dict,
    *,
    work_root: str | None = None,
    time_limit: float = 300.0,
    memory_bytes: int = 256 * 1024 * 1024,
    max_processes: int = 4,
) -> dict:
    """Execute one assignment in a sandboxed child; return its result payload."""
    job = native.create_limited_job(memory_bytes, max_processes)
    process = None
    thread = None
    try:
        try:
            token = native.low_integrity_token()
            boundary = "job-object + low-integrity"
        except native.SandboxUnavailable:
            # Unelevated dev shell: the Job Object still caps memory/processes
            # and kills orphans, but filesystem writes are NOT kernel-denied.
            # Loud, not silent — pretending otherwise would be a lie.
            print("[worker] sandbox: low-integrity token unavailable "
                  "(needs elevation) — job-object limits only", flush=True)
            token = None
            boundary = "job-object-only"
        print(f"[worker] sandbox boundary: {boundary}", flush=True)
        try:
            work_dir = _make_granted_work_dir(work_root)
            try:
                payload = json.dumps({**assignment, "work_dir": str(work_dir)}) + "\n"
                process, thread, write_fd, read_fd = _spawn(job, token, work_dir)
                try:
                    _write_all(write_fd, payload.encode("utf-8"))
                finally:
                    os.close(write_fd)
                result = _parse(_read_line_with_timeout(read_fd, time_limit))
                if result["status"] == "__timeout__":
                    native.terminate_and_close(job)
                    job = None  # terminated + closed by the call above
                    result = {
                        "status": "failed",
                        "error": f"sandbox: unit timeout after {time_limit}s",
                    }
                return result
            finally:
                _cleanup(work_dir)
        finally:
            if token is not None:
                native._close_handle(token)
    finally:
        if job:
            native.terminate_and_close(job)
        if process:
            native._close_handle(process)
        if thread:
            native._close_handle(thread)


# ---- child spawn -------------------------------------------------------------


class _RawWriter:
    def __init__(self, raw):
        self.writable_handle = raw


class _RawReader:
    def __init__(self, raw):
        self.readable_handle = raw


def _spawn(job, token, work_dir: Path):
    """Create the suspended child, assign it to the job, resume it, wire pipes."""
    import msvcrt

    from worker.sandbox.launch import build_command_line, create_suspended_process
    from worker.sandbox.launch import resume as resume_thread

    parent_read, child_write = os.pipe()  # child stdout -> parent
    child_read, parent_write = os.pipe()   # parent stdin  -> child
    # The child's ends must be inheritable; the parent's must NOT be
    # (otherwise the child keeps the pipe open and EOF never arrives).
    os.set_inheritable(child_write, True)
    os.set_inheritable(child_read, True)

    cmdline = build_command_line(sys.executable, ["-m", "worker.sandbox.runner"])
    process, thread = create_suspended_process(
        cmdline,
        cwd=str(_REPO_ROOT),
        env=_child_env(),
        stdin=_RawWriter(msvcrt.get_osfhandle(child_read)),
        stdout=_RawReader(msvcrt.get_osfhandle(child_write)),
        stderr=None,
        token=token,
    )
    native.assign_process_to_job(job, process)
    resume_thread(thread)
    # Close the child's ends in the parent so EOF propagates correctly.
    os.close(child_read)
    os.close(child_write)
    return process, thread, parent_write, parent_read


def _child_env() -> dict:
    env = dict(os.environ)
    paths = [str(_REPO_ROOT), str(_APPS_WORKER)]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        view = view[written:]


def _read_line_with_timeout(fd: int, timeout: float) -> str:
    """One line (or "") within `timeout` seconds; "__timeout__" sentinel on expiry.

    The reader thread is a daemon: if the child ignores the job kill, the
    process exit still reaps it, and the pipe dies with the child.
    """
    box: dict[str, str] = {}
    done = threading.Event()

    def _read() -> None:
        try:
            box["line"] = os.read(fd, 1 << 20).decode("utf-8", "replace").strip()
        except OSError:  # pipe closed early (child died) is a normal outcome
            box["line"] = ""
        finally:
            done.set()

    threading.Thread(target=_read, daemon=True).start()
    if not done.wait(timeout):
        return "__timeout__"
    return box.get("line", "")


# ---- work dir ---------------------------------------------------------------


def _make_granted_work_dir(work_root: str | None):
    root = work_root or os.environ.get("WORK_ROOT") or str(_REPO_ROOT)
    work_dir = Path(tempfile.mkdtemp(prefix="unit-sbx-", dir=root))
    try:
        # Harmless when it fails: the label only matters for the
        # low-integrity path, which checks availability separately.
        native.grant_write_access(work_dir)
    except Exception:  # noqa: BLE001 - labeling is best-effort, not correctness
        pass
    return work_dir


def _cleanup(path) -> None:
    shutil.rmtree(path, ignore_errors=True)


# ---- output parsing ----------------------------------------------------------


def _parse(line: str) -> dict:
    if line == "__timeout__":
        return {"status": "__timeout__"}
    if not line:
        return {"status": "failed", "error": "sandbox: no output from child"}
    try:
        payload = json.loads(line.splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        return {"status": "failed", "error": f"sandbox: bad child output: {exc}"}
    if not isinstance(payload, dict) or "status" not in payload:
        return {"status": "failed", "error": "sandbox: malformed child result"}
    return payload


def sandbox_available() -> bool:
    return native.available()
