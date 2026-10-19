"""Sprint 36 exit proof: onboard an outside participant end-to-end.

Reproduces the documented participant journey (``docs/getting-started.md``)
against a live coordinator using only the commands and public endpoints a real
participant would use -- no privileged shortcuts and no developer help:

    mint token (operator) -> worker --setup -> worker --enroll -> worker --loop
    -> submit a small job -> assert: joined, received work, earned credit.

For automation it can also mint the enrollment token itself (the operator's
documented step) with ``--mint``, so a single command proves the whole loop:

    python scripts/onboard_participant.py --coordinator-url http://127.0.0.1:8000 --mint

Exit code 0 only when the participant reached the exit condition:
``joined`` AND ``received_work`` AND ``earned_credit``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# The documented participant steps, in order (docs/getting-started.md).
DOCUMENTED_STEPS = [
    "get the worker (bundle or source)",
    "worker --setup (coordinator, token, limits)",
    "worker --enroll <token> --coordinator-url <url>",
    "worker --loop (receive + execute work)",
    "verify contribution credit (worker --status / dashboard 'My node')",
]

# Every painpoint a participant could hit has a documented remedy.
SUPPORT_DOCS = ["docs/getting-started.md", "docs/support.md"]

# The only endpoints this proof touches; all are documented for participants
# or operators and are public/read-only except the two POSTs below.
DOCUMENTED_ENDPOINTS = [
    "POST /auth/enrollment-tokens",
    "POST /auth/enroll",
    "POST /jobs",
    "GET /workers/{worker_id}",
    "GET /workers/{worker_id}/stats",
    "GET /workers/{worker_id}/credits",
    "GET /workloads",
]


def plan() -> list[str]:
    """Ordered documented steps a participant follows."""
    return list(DOCUMENTED_STEPS)


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())


def _try_get(url: str) -> dict | None:
    try:
        return _get(url)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return None


def _post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def summarize(worker: dict | None, stats: dict | None, credits: dict | None) -> dict:
    """Verdict for the exit condition from the participant's public view."""
    online = bool(worker) and worker.get("status") in ("online", "paused", "throttled")
    received = bool(stats) and (
        stats.get("attempts", 0) > 0 or stats.get("completed_units", 0) > 0
    )
    earned = bool(credits) and credits.get("earned", 0) > 0
    return {
        "joined": bool(worker),
        "online": online,
        "received_work": received,
        "earned_credit": earned,
        "completed_units": (stats or {}).get("completed_units", 0),
        "credit_balance": (credits or {}).get("balance", 0),
        "credit_earned": (credits or {}).get("earned", 0),
        "ok": bool(worker) and received and earned,
    }


def render(summary: dict) -> str:
    def mark(ok: bool) -> str:
        return "yes" if ok else "NO"

    return "\n".join([
        "outside-participant onboarding proof",
        f"  joined               : {mark(summary['joined'])}",
        f"  online (contributing): {mark(summary['online'])}",
        (
            f"  received work        : {mark(summary['received_work'])} "
            f"({summary['completed_units']} units completed)"
        ),
        (
            f"  earned credit        : {mark(summary['earned_credit'])} "
            f"(balance {summary['credit_balance']}, earned {summary['credit_earned']})"
        ),
        f"  exit condition met   : {mark(summary['ok'])}",
    ])


def _worker_cmd(worker_exe: str | None) -> list[str]:
    if worker_exe:
        return [worker_exe]
    return [sys.executable, str(REPO_ROOT / "apps" / "worker" / "worker" / "main.py")]


def _run(cmd: list[str], env: dict, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, input=stdin, env=env, capture_output=True, text=True, timeout=180, check=False
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sprint 36 participant onboarding proof")
    parser.add_argument("--coordinator-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token", default=None, help="participant enrollment token")
    parser.add_argument("--mint", action="store_true", help="mint the token (operator step)")
    parser.add_argument("--note", default="onboarding-proof")
    parser.add_argument("--worker-exe", default=None, help="prebuilt worker.exe (bundle path)")
    parser.add_argument("--work-dir", default=None)
    parser.add_argument("--duration", type=float, default=30.0, help="max seconds to observe work")
    args = parser.parse_args(argv)

    base = args.coordinator_url.rstrip("/")
    work_dir = Path(args.work_dir) if args.work_dir else Path(
        tempfile.mkdtemp(prefix="cc-onboard-")
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    id_file = work_dir / ".worker_id"
    env = {**os.environ, "WORKER_ID_FILE": str(id_file)}
    worker = _worker_cmd(args.worker_exe)

    print(f"coordinator: {base}")
    print(f"work dir   : {work_dir}")
    print(f"steps      : {' -> '.join(plan())}")

    token = args.token
    if not token and args.mint:
        minted = _post(f"{base}/auth/enrollment-tokens", {"note": args.note})
        token = minted["token"]
        print(f"minted enrollment token {minted.get('id', '?')} (operator step)")
    if not token:
        print("ERROR: need --token (participant) or --mint (operator bootstrap)", file=sys.stderr)
        return 2

    # Wizard answers, in prompt order: coordinator, token, idle-only=n,
    # max cpu=100, max gpu=100, no temperature ceiling, battery=allow, no
    # hours window, no bandwidth cap, autostart=no. On a machine whose GPU
    # cannot be measured the wizard omits the two GPU prompts (extra answers
    # are simply unread), which is exactly the behaviour we want to prove.
    answers = f"{base}\n{token}\nn\n100\n100\n\nallow\n\n\nn\n"
    setup = _run(worker + ["--setup"], env, stdin=answers)
    print("\n[1/4] worker --setup")
    print((setup.stdout or setup.stderr or "").strip()[-1500:])
    if setup.returncode != 0:
        print("setup failed", file=sys.stderr)
        return 1

    print("\n[2/4] worker --enroll")
    enrolled = _run(
        worker + ["--enroll", token, "--coordinator-url", base, "--worker-id-file", str(id_file)],
        env,
    )
    print((enrolled.stdout or enrolled.stderr or "").strip())
    if enrolled.returncode != 0:
        print("enroll failed", file=sys.stderr)
        return 1

    credential = json.loads((work_dir / "credential.json").read_text(encoding="utf-8"))
    worker_id = credential["worker_id"]

    print("\n[3/4] submit a small job (so there is work to receive)")
    _post(f"{base}/jobs", {
        "workload_type": "hello_compute",
        "params": {"op": "sum"},
        "total_units": 4,
        "chunk_size": 1,
        "verify_sample": 1.0,
    })

    print("[4/4] worker --loop (contributing)")
    loop = subprocess.Popen(
        worker + [
            "--coordinator-url", base, "--loop", "--interval", "1",
            "--heartbeat-interval", "5", "--no-ws", "--worker-id-file", str(id_file),
            "--work-root", str(work_dir / "work"),
        ],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )

    summary = summarize(None, None, None)
    deadline = time.time() + args.duration
    try:
        while time.time() < deadline:
            worker_state = _try_get(f"{base}/workers/{worker_id}")
            stats = _try_get(f"{base}/workers/{worker_id}/stats")
            credits = _try_get(f"{base}/workers/{worker_id}/credits")
            summary = summarize(worker_state, stats, credits)
            if summary["ok"]:
                break
            time.sleep(1.0)
    finally:
        loop.terminate()
        try:
            loop.wait(timeout=10)
        except subprocess.TimeoutExpired:
            loop.kill()

    print()
    print(render(summary))
    if not summary["ok"]:
        print("\nworker log tail:")
        assert loop.stdout is not None
        print(loop.stdout.read()[-2000:])
        return 1
    print(f"\nparticipant {worker_id} onboarded without developer assistance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
