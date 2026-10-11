# CommunityCompute — Community-Powered Distributed Compute Network

> Community-powered distributed compute network that turns idle consumer PCs into a pool of AI/compute workers.

**Status:** Sprint 2 — worker registration; `GET /workers` lists connected workers. See `docs/roadmap.md`, `docs/architecture.md`, `docs/implementation-guide.md`.

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

# 2. Worker A registers (terminal 2; idempotent — safe to re-run)
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --once

# 3. Worker B registers with its own ID file (simulates 2nd PC locally;
#    on the real 2nd PC just run step 2 against http://192.168.4.68:8000)
python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --once --worker-id-file .worker_id_b

# 4. Both workers appear with unique IDs
# → http://127.0.0.1:8000/workers

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
