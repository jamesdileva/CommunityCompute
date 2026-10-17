# CommunityCompute — Community-Powered Distributed Compute Network

> Community-powered distributed compute network that turns idle consumer PCs into a pool of AI/compute workers.

**Status:** Sprint 30 - customer workload isolation (per-customer quotas, signed workload definitions, tenant-scoped jobs at `/api/v1`).

## Core loop (stable abstraction)

```text
Job → Work Units → Capability Matcher → Worker Lease → Execution → Verification → Result
```

## Repo layout

```text
apps/coordinator/   FastAPI control plane (Sprint 1+: /health, SQLite, scheduler)
apps/worker/        Python daemon: heartbeat, execution, policy (Sprint 2+: registration)
apps/dashboard/     React + TS + Vite (thin until protocol stabilizes, Sprint 16)
packages/protocol/      versioned Worker↔Coordinator messages
packages/workload-spec/ workload requirement schemas
packages/shared-types/  shared types
workloads/hello-compute/ deterministic first workload (Sprint 6)
tests/integration/  tests/end_to_end/
scripts/            collect_baseline.py, check_lan.py
docs/               architecture, implementation-guide, roadmap, baselines
```

## Sprint 2 quickstart (Windows, Python 3.12+, Node LTS)

```powershell
# 1. Coordinator (terminal 1)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir apps/coordinator
# → http://127.0.0.1:8000/health returns {"status":"ok",...,"database":{"connected":true,...}}
# DB file communitycompute.db is created on startup (gitignored, dev-local).

# 2. Worker A registers + reports capabilities (terminal 2)
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --once
# → console prints discovered CPU/RAM/GPU (adapter providers: nvidia-smi → Win32 → Unknown)

# 3. Worker B registers with its own ID file (simulates 2nd PC locally;
#    on the real 2nd PC just run step 2 against http://192.168.4.68:8000)
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --once --worker-id-file .worker_id_b

# 4. Both workers + capability profiles visible
# → http://127.0.0.1:8000/workers  and  http://127.0.0.1:8000/workers/{id}

# 5. Keep the worker alive in loop mode (registers once, then heartbeats)
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --loop --interval 15
# → GET /workers shows online + live cpu/ram; stopping it flips to offline
#   after HEARTBEAT_TIMEOUT_SECONDS (default 60)

# 6. Submit a job (deterministic hello-compute) — Sprint 5
#    POST http://127.0.0.1:8000/jobs
#    {"workload_type":"hello_compute","params":{"op":"sum"},
#     "total_units":1000,"chunk_size":100}
# → GET /jobs/{id} shows exactly 10 work units (1-100 ... 901-1000)

# 7. M1: run two workers on one machine, both pull from the same job — Sprint 6
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --loop --interval 2 --worker-id-file .worker_id_a
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --loop --interval 2 --worker-id-file .worker_id_b
# submit e.g. total_units 20, chunk_size 1 → both workers claim units,
# coordinator verifies each result, job completes with aggregate final=210

# 5. Hardware baseline (this PC)
python scripts/collect_baseline.py --out docs/baseline-james.json

# 6. LAN check (second PC must reach this host:port)
python scripts/check_lan.py --host 192.168.4.68 --port 8000
```

Copy `.env.example` to `.env` (never commit `.env`) for local overrides.

## Sprint workflow

Every sprint: **Plan → Scope → Implement → Verify (tests) → Commit+Push**. See `AGENTS.md` §4 and `worklog.md` (append-only journal).

## Tests

```powershell
python -m pytest apps/coordinator/tests apps/worker/tests -v
```

## Non-goals (prototype)

No crypto, real-money payouts, public Internet execution, arbitrary code execution, K8s, or distributed LLM training — see architecture §2.
