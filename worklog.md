# worklog.md — CreatorLab running journal (append-only)

> Log every sprint: date (UTC), sprint, goal, scope, changes, tests + outcome, decisions, next steps. Never rewrite history — append new entries.

---

## Template (copy for each sprint)

```markdown
## YYYY-MM-DD — Sprint N: <Title>
**Goal:** ...
**Scope (in / out):**
- In: ...
- Out: ...
**Exit condition (verbatim from roadmap):** ...
**Changes:**
- ...
**Tests run:**
- `...` → pass/fail (...)
**Decisions:**
- ...
**Next steps:**
- ...
```

---

## 2026-10-11 — Bootstrap: AGENTS.md + worklog.md + repo setup
**Goal:** Adopt sprint workflow (Plan → Scope → Implement → Verify → Commit+Push); create GitHub repo `CreatorLab` (public).
**Scope (in / out):**
- In: review docs; add AGENTS.md + worklog.md; `git init` + `gh repo create CreatorLab --public`; Sprint 0 plan.
- Out: any Sprint 0 implementation code (repo skeleton, coordinator/worker code) — that is Sprint 0 proper.
**Exit condition:** `gh repo view` shows `CreatorLab` public repo; `main` has initial commit with docs + AGENTS.md + worklog.md.
**Changes:**
- Added AGENTS.md (sprint workflow, tech stack, conventions), worklog.md (this file), .gitignore
- `git init -b main` + initial commit `f386130 docs(bootstrap): add AGENTS.md, worklog.md, docs baseline`
- `gh repo create CreatorLab --public` → https://github.com/jamesdileva/CreatorLab (PUBLIC), pushed `main`
**Tests run:**
- `git status` → clean, on `main` tracking `origin/main`
- `gh repo view --json name,description,visibility,url` → CreatorLab / PUBLIC / correct description — pass
**Decisions:**
- Repo name: `CreatorLab` (public). Description from architecture.md §1: "Community-powered distributed compute network that turns idle consumer PCs into a pool of AI/compute workers."
- Workflow per sprint: Plan → Scope → Implement → Verify (tests) → Commit+Push.
**Next steps:**
- Sprint 0: env baselines, LAN check, skeleton, .env.example, README, minimal coordinator+worker processes.

---

## 2026-10-11 — Sprint 0: Project Definition & Environment
**Goal:** Repository skeleton, dev environments, LAN reachability, hardware baselines, conventions (roadmap Sprint 0).
**Scope (in / out):**
- In (Full Sprint 0): skeleton dirs; README; .env.example; pyproject.toml; minimal coordinator `/health`; minimal worker ping (`--once`/`--loop`, persistent UUID); dashboard Vite stub; protocol/workload-spec/shared-types stubs; hello-compute stub; scripts/collect_baseline.py + check_lan.py; this-PC baseline; local + LAN verify; pytest suites.
- Out: Sprint 1+ work (SQLite/models/logging/error handling, registration endpoint, capability discovery, heartbeat loop, second-PC baseline — needs Iris Xe laptop).
**Exit condition (verbatim from roadmap):**
```text
PC A ──> Coordinator
PC B ──> Coordinator
```
Proven locally (PC A = this PC `james` 192.168.4.68 → localhost coordinator); PC B pending second machine running same worker command.
**Changes:**
- Root: README.md, .env.example, pyproject.toml (pytest pythonpath), .gitignore (+.worker_id)
- Coordinator: app/__init__.py, app/main.py (/health), requirements.txt, tests/test_health.py
- Worker: worker/__init__.py, worker/config.py (UUID, never hostname), worker/main.py (ping, --once/--loop), requirements.txt, tests/test_worker_id.py + test_ping.py
- Dashboard: package.json, vite.config.ts, tsconfig.json, index.html, src/main.tsx + App.tsx (Sprint 16 stub)
- Packages: protocol/__init__.py (PROTOCOL_VERSION) + README, workload-spec/README, shared-types/README
- workloads/hello-compute/README, tests/integration + end_to_end READMEs
- Scripts: collect_baseline.py (nvidia-smi → Win32_VideoController → Unknown), check_lan.py (resolve+TCP+/health)
- Baseline: docs/baseline-james.json (Windows 11, AMD 6c/12t 3.6GHz, 16GB RAM, AMD Radeon RX 6400 4GB, driver 32.0.21045.5002)
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 5 passed
- Live: uvicorn coordinator :8000 + `worker/main.py --once` → ping OK `{'status':'ok',...}` — pass
- `scripts/check_lan.py --host 127.0.0.1 --port 8000` → resolve OK, tcp OK, GET /health 200 — pass
- `scripts/collect_baseline.py --out docs/baseline-james.json` → exit 0, GPU detected via Win32_VideoController — pass
- Dashboard: `npm install` (68 pkgs, 12s) + `npm run build` (tsc + vite, 1.18s) — pass
- Env: Python 3.14.3, Node v24.14.1, npm 11.11.0, SQLite 3.53.4, fastapi 0.139.0, sqlalchemy 2.0.51, psutil 7.2.2
**Decisions:**
- Python 3.14.3 satisfies "3.12+" requirement; no venv (global toolchain already has fastapi/uvicorn/sqlalchemy/pytest).
- Removed apps/*/tests/__init__.py (duplicate `tests` package collided on pythonpath); unique test module names instead.
- Fixed test httpx.Response mock (needs request=...), check_lan arrow `→`→`->` (cp1252 console), worker sys.path bootstrap for direct script run.
- `.worker_id` gitignored (per-machine identity); baseline JSON committed as Sprint 0 evidence.
- Dashboard stays stub until Sprint 16; protocol stays version-string-only until Phase 2.
**Next steps:**
- Sprint 1: coordinator skeleton (config, SQLite, SQLAlchemy worker table, logging, error handling, /health+DB check).
- Need Iris Xe laptop: run baseline script + worker `--coordinator-url http://192.168.4.68:8000 --once` for PC B exit proof.

---

## 2026-10-11 — Rename: GitHub repo CreatorLab → CommunityCompute
**Goal:** Align GitHub repo name with project/folder name `CommunityCompute` (local folder was always correct; `CreatorLab` was just the initial repo-name suggestion).
**Scope (in / out):**
- In: `gh repo rename CommunityCompute --yes`; `git remote set-url origin`; replace `CreatorLab`→`CommunityCompute` in AGENTS.md, README, .env.example, coordinator/worker strings, dashboard package + UI stub, protocol docstring; verify tests + push.
- Out: rewriting history entries below (append-only — old entries keep `CreatorLab` name as record).
**Changes:**
- `gh repo rename CommunityCompute --yes -R jamesdileva/CreatorLab` → https://github.com/jamesdileva/CommunityCompute (PUBLIC, same description)
- Renamed references in 12 files (incl. `creatorlab-dashboard` → `communitycompute-dashboard` in package.json + package-lock.json)
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 5 passed
- `gh repo view jamesdileva/CommunityCompute --json name,description,visibility,url` → CommunityCompute / PUBLIC — pass
**Decisions:**
- Old URL `github.com/jamesdileva/CreatorLab` auto-redirects to the new name (GitHub keeps redirect on rename).
**Next steps:**
- Sprint 1: coordinator skeleton (done below).

---

## 2026-10-11 — Sprint 1: Coordinator Skeleton
**Goal:** Central control service; `GET /health` proves alive + SQLite-connected (roadmap Sprint 1).
**Scope (in / out):**
- In (Full Sprint 1): config (pydantic-settings), SQLite engine/session/Base, Worker table, basic logging, JSON error envelope, `/health` with `SELECT 1` + worker count; tests for each.
- Out: registration/heartbeat endpoints (S2/S4), capabilities (S3), jobs/work units (S5), auth/TLS, migrations (dev DB disposable), dashboard changes.
**Exit condition (verbatim from roadmap):** Opening `/health` proves the coordinator is alive and connected to SQLite.
**Changes:**
- New: app/config.py (COORDINATOR_HOST/PORT, DATABASE_URL default `sqlite:///./communitycompute.db`, LOG_LEVEL), app/db/__init__.py (engine with `check_same_thread=False`, SessionLocal, Base, init_db, get_db, check_database), app/models/worker.py (workers: UUID PK, version, hostname, status default `unknown`, first/last seen, updated_at), app/api/health.py (/health router, 503 on DB loss), app/main.py (lifespan init_db, logging, 404/422/500 JSON envelope), placeholder scheduler/services/schemas packages
- Rewrote: tests/test_health.py (tmp-DB dependency override; health+count+envelope tests); new tests/test_worker_model.py + test_config.py
- Touched: .env.example (+DATABASE_URL), README (DB note)
**Tests run:**
- `python -m pytest apps/coordinator/tests apps/worker/tests -p no:randomly` → 11 passed
- Live uvicorn: `/health` → 200 `{'status':'ok','database':{'connected':True,'workers':0}}` — pass
- `GET /nope` → 404 `{'error':{'code':404,...}}` — pass
- Sprint-0 worker `--once` → ping OK (stable ID `a4228558…`, version string bumped) — pass
- `communitycompute.db` created on startup; `.tables` → `workers`; `SELECT count(*)` → 0 — pass
**Decisions:**
- Target package layout (api/scheduler/services/models/schemas/db) adopted now to avoid later churn; empty packages carry landing-note docstrings.
- `/health` depends on `get_db` so tests override with tmp DBs — no test pollution of dev DB.
- No Alembic: dev SQLite file is disposable (gitignored); migrations only when data worth keeping exists.
**Next steps:**
- Sprint 2: worker skeleton (config, persistent ID already done, registration endpoint + startup/shutdown).
