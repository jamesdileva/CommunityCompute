# AGENTS.md — CommunityCompute (Community AI Compute Network)

This file guides all agents (and humans) working in this repo. Follow it unless the user explicitly overrides.

## 1. Project Overview

**CommunityCompute** is a community-powered distributed compute network that turns idle consumer PCs into a pool of AI/compute workers. See `docs/architecture.md` for the full vision.

Core abstraction (must stay stable as the network grows):

```text
Job → Work Units → Capability Matcher → Worker Lease → Execution → Verification → Result
```

- A **Job** is a logical workload (e.g. generate 1,000 images).
- A **Job** is decomposed into **Work Units** — the smallest independently executable piece of work.
- The **Scheduler** assigns work units, not vague jobs.
- Workers are heterogeneous and unreliable — work units must be **retryable, idempotent, leased with expiry**.

Key docs:
- `docs/architecture.md` — system architecture, components, decisions (source of truth for design)
- `docs/implementation-guide.md` — phased build order, protocol sketches, testing strategy
- `docs/roadmap.md` — sprints 0–40+, milestones M1–M9, exit conditions per sprint

Prototype hardware: 1× PC ~4GB VRAM + 1× laptop Intel Iris Xe. Two-node LAN first, Internet later.

Non-goals for prototype: distributed LLM training/inference, crypto, real-money payouts, public Internet execution, production multi-tenant security, million-node scale.

## 2. Repository Structure (target, per architecture §23)

```text
CommunityCompute / community-ai-compute/
├── apps/
│   ├── coordinator/      # FastAPI + Scheduler + SQLite (control plane)
│   │   ├── app/{api,scheduler,services,models,schemas,db}/ + main.py
│   │   └── tests/
│   ├── worker/           # Python daemon: discovery, heartbeat, execution, policy
│   │   ├── worker/{capabilities,monitoring,execution,networking,policy,storage}/ + main.py
│   │   └── tests/
│   └── dashboard/        # React + TypeScript + Vite (contributor + network views)
│       ├── src/{pages,components,services,types}/
│       └── tests/
├── packages/
│   ├── protocol/         # versioned Worker↔Coordinator messages
│   ├── workload-spec/
│   └── shared-types/
├── workloads/            # hello-compute, image-batch, video-batch, ...
├── tests/{integration,end_to_end}/
├── docs/                 # architecture, implementation-guide, roadmap
├── scripts/ docker/
├── AGENTS.md  worklog.md  README.md  .env.example  .gitignore
```

`apps/coordinator` and `apps/worker` must be independently runnable. Keep the dashboard thin until the worker protocol stabilizes.

## 3. Tech Stack (pinned by architecture §22)

- Worker: Python 3.12+, `psutil`, PySide6 (tray UI later), `httpx`, `websockets`
- Backend: Python 3.12+, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2.x, SQLite (prototype) → PostgreSQL later
- Frontend: React + TypeScript + Vite
- Packaging: PyInstaller (Windows worker, later MSIX/signed releases)
- AI runtimes via adapter interface — never hardcode one runtime (Ollama, llama.cpp, ONNX, PyTorch, DirectML, CUDA, ROCm are future backends)

Check `python --version` (expect 3.12+) and `node --version` (LTS) before starting work.

## 4. Sprint Workflow (mandatory)

Every sprint follows **Plan → Scope → Implement → Verify → Commit+Push**. Do not skip steps.

1. **Plan**: read the sprint section in `docs/roadmap.md` + relevant `docs/implementation-guide.md` phase. Write a sprint plan (goals, files to touch, API/contracts, tests to add).
2. **Scope**: confirm in/out of scope with user. Record scope + exit condition (verbatim from roadmap) in `worklog.md`. Smallest complete loop first — maintain a working system every sprint.
3. **Implement**: build in small integrated increments (new component → integrate → test → verify → commit → next). No 10 disconnected components merged at the end.
4. **Verify (tests)**: run relevant tests before asking to commit:
   - `pytest apps/coordinator/tests apps/worker/tests` (unit + integration)
   - New code requires new tests: capability detection, compat matching, policy engine, work-unit creation, state transitions, result verification.
   - Failure tests where roadmap demands them (kill worker, drop network, restart coordinator, duplicate/expired/malformed payloads).
   - Record commands + results in `worklog.md`.
5. **Commit + Push**: only after verification passes. Conventional commits (`feat(sprint-0): ...`, `fix(...)`, `test(...)`, `docs(...)`). Push to `main` on `CommunityCompute` GitHub repo. Never commit secrets (`.env`); only `.env.example`.

Update `worklog.md` at sprint start, during key decisions, and at sprint close.

## 5. Coding Conventions

- Python: type hints, `ruff`/`black` compatible formatting, Pydantic v2 for all API schemas, SQLAlchemy 2.x typed models.
- Protocol first: define/version messages in `packages/protocol/` before building scheduler logic. Suggested messages: `WorkerRegistration`, `Heartbeat`, `WorkUnit`, `WorkResult` (see implementation-guide §4). Never use hostname as identity — persistent generated UUID node ID.
- Scheduler: FIFO first, no scoring until correctness proven. Compatibility filter order per architecture §10 (online → available → OS/runtime → GPU vendor/API → VRAM → CPU → RAM → policy → network/storage → worthwhile).
- Worker must **fail closed**: reject work exceeding declared limits or unsatisfiable requirements; validate protocol version, workload type, resource limits, runtime, payload size, policy before executing.
- Leases, not just "running": `lease_id, worker_id, started_at, expires_at, attempt_number`. Expiry → requeue.
- No large binaries in SQLite. Model files cached locally, reused across work units; worker reports `installed_workloads, cached_models, model_versions`.
- Security: TLS everywhere (later sprints), outbound-only worker connections (no inbound firewall ports), allowlisted workloads only, temp dirs + cleanup, no user-doc access, no arbitrary shell, audit logging.
- Frontend: TypeScript strict, minimal dashboard (node status, GPU/CPU/RAM/temp, current work, pause; network: online workers, queued/running/completed/failed, throughput).

## 6. Testing Conventions

Per implementation-guide §32, maintain three layers:

- `apps/*/tests/` — unit (pytest)
- `tests/integration/` — registration, heartbeat, job submit, leasing, result submit
- `tests/end_to_end/` — two real machines: submit → distribute → execute → return → verify → aggregate

Deterministic workloads first (`hello-compute`: sum/hash over number ranges) so verification is exact (expected hash). Corrupted results must be rejected.

## 7. Safety / Limits

- Never implement payments, public registration, arbitrary code execution, K8s, or blockchain in early sprints.
- No W3 (tightly-coupled/distributed training) work — W1 independent workloads only until M4.
- Do not introduce Postgres/Redis/object-storage until SQLite/single-scheduler measurably insufficient.
- Do not open public enrollment before sandboxed-execution milestone (Sprint 22) is satisfactory.
- Ask before: changing the protocol, adding dependencies, touching auth/security, `gh repo` / destructive git ops.

## 8. GitHub Workflow

- Repo: `CommunityCompute` (public). Description: "Community-powered distributed compute network that turns idle consumer PCs into a pool of AI/compute workers."
- Remote: `origin` → `github.com/<owner>/CommunityCompute`, default branch `main`.
- Flow: `git status` → stage intended files only → `git diff --cached` review → conventional commit → `git push`.
- PRs only when asked; otherwise direct to `main` per-sprint after verification.

## 9. Worklog

`worklog.md` is the running journal. Every entry: date (UTC), sprint, goal, scope, changes, tests run + outcome, decisions, next steps. Keep it append-only — never rewrite history.
