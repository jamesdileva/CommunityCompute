# Private Community Beta — operator runbook (Sprint 26)

How to invite trusted machines, watch them, and remove them. Everything
below works today; the two-machine and cross-network proofs stay pending
until a second network is available (mocked locally via `beta_swarm.py`).

## 1. Invite (mint enrollment tokens)

```powershell
# one token per machine/person (single-use, optionally expiring)
python -c "import httpx; print(httpx.post('http://127.0.0.1:8000/auth/enrollment-tokens', json={'note': 'laptop-alice', 'ttl_minutes': 1440}, timeout=5).json())"
```

Send the `token` value (and only that value) to the contributor over a
trusted channel. Listing/auditing: `GET /auth/enrollment-tokens`.

## 2. Join (contributor side, no dev environment needed)

```powershell
python apps/worker/worker/main.py --setup          # guided: URL, token, limits
python apps/worker/worker/main.py --enroll <token> --coordinator-url http://<pc-a>:8000
python apps/worker/worker/main.py --coordinator-url http://<pc-a>:8000 --loop
```

Or install the bundle (Sprint 24): `scripts/build_worker.ps1` →
`dist/worker/worker.exe --setup`.

## 3. Monitor (no database access needed)

- `GET /network/summary` — workers by status, queue depths, throughput.
- `GET /network/capacity` — online cores/RAM, GPUs by tier/vendor, cached
  models, runtimes, worker versions, queued depth. This is the capacity
  view to watch before inviting more load.
- `GET /workers/{id}/reputation` — reliability score + conduct history.
- `GET /workers/{id}/stats` — contribution totals.
- Ask contributors for `worker --diagnostics` output on support requests
  (redacted by construction — no bearer tokens inside).

## 4. Maintain

- Outdated worker: `MIN_WORKER_VERSION=0.1.0` env → old workers get 426
  `worker update required` on claim (they keep heartbeating; they just get
  no new work). Tell the contributor to fetch a fresh build (`--check-update`).
- Hoarding worker: `MAX_LEASES_PER_WORKER` (default 8) caps simultaneous
  leases per worker; excess claims get `{}` until leases resolve.
- Misbehaving worker: `POST /workers/{id}/revoke` — bearer dies on its next
  request; `POST /workers/{id}/pause` freezes claims without killing identity.
- Rotate a single credential without touching enrollment:
  `POST /workers/{id}/rotate-credential` (old token dies immediately).

## 5. Leave / offboard

1. Contributor stops the worker (tray Quit / Ctrl+C) or operator pauses it.
2. Operator revokes: `POST /workers/{id}/revoke`.
3. Contributor runs `scripts/uninstall_worker.ps1` (removes auto-start,
   optionally wipes id/policy/credential/models/logs).

## What "mocked" means right now

`scripts/beta_swarm.py` runs the whole join → work → kill → pause/resume →
complete cycle with N isolated worker processes on one machine. It proves
the coordination needs no manual database intervention. It does NOT prove
cross-machine networking, installer UX on a clean PC, or real human
contributors — those stay explicitly pending.
