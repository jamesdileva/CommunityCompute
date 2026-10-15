"""Sandboxed unit runner (Sprint 22): child-process entry point.

Protocol: one JSON assignment on stdin (a single line), one JSON result on
stdout (a single line). Process exit code is 0 on a `completed` result and
1 otherwise, so the parent can treat a crash as a failed unit.

The child runs `run_unit` — the same executor registry the worker loop
uses — but inside the sandboxed process with an injected `work_dir`.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    line = sys.stdin.readline()
    if not line.strip():
        print(json.dumps({"status": "failed", "error": "empty assignment"}))
        return 1
    try:
        assignment = json.loads(line)
    except json.JSONDecodeError as exc:
        print(json.dumps({"status": "failed", "error": f"bad assignment json: {exc}"}))
        return 1

    work_dir = assignment.get("work_dir")
    if not work_dir:
        print(json.dumps({"status": "failed", "error": "assignment missing work_dir"}))
        return 1

    from worker.execution.registry import run_unit

    sleep_seconds = assignment.get("sleep_seconds")
    if sleep_seconds:
        # Deliberate test hook: time-box proof (never set by real payloads).
        import time as _time

        _time.sleep(float(sleep_seconds))
    alloc_mb = assignment.get("alloc_mb")
    if alloc_mb:
        # Deliberate test hook: memory-cap proof. Allocates AND touches the
        # pages (untouched virtual memory is never committed, so touching is
        # what actually trips the job's memory cap).
        chunk = bytearray(1024 * 1024)
        pages = []
        for _ in range(int(alloc_mb)):
            pages.append(bytearray(chunk))
            pages[-1][::4096] = b"\x01" * (len(pages[-1]) // 4096)
        _HOLD.append(pages)
    result = run_unit(assignment, work_root=None)
    payload = {
        "status": result.status,
        "value": result.value,
        "output_hash": result.output_hash,
        "error": result.error,
        "execution_ms": result.execution_ms,
        "metrics": result.metrics,
    }
    print(json.dumps(_jsonable(payload)))
    return 0 if result.status == "completed" else 1


def _jsonable(value: object) -> object:
    """Best-effort JSON scrub for exotic values (never raises)."""
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return json.loads(json.dumps(value, default=str))


# Holds greedy allocations alive for the memory-cap proof (test hook only).
_HOLD: list = []


if __name__ == "__main__":
    sys.exit(main())
