# Public Beta Readiness — Go / No-Go (Sprint 35)

**Decision (2026-10-18):**

> **NO-GO for open public worker enrollment.**
> **GO for an invited, allowlisted prototype beta** of trusted, technical
> contributors running supported workloads on a trusted network.

This is the roadmap Sprint 35 exit condition: *a documented go/no-go decision
for public worker enrollment.* The decision is mirrored as live, checkable data
at `GET /beta/readiness` (see `app/services/readiness.py`), so it is evidence,
not prose alone.

## Why this decision

The prototype has, and can demonstrate, every **control** a small beta needs:
identity, revocation, signed assignments, allowlisted workloads, deterministic
verification, resource limits, customer isolation, an audit trail, telemetry
retention, a privacy notice, participation terms, and an incident runbook.

It does **not** yet have the things that make enrollment of *the general
public on the open internet* responsible. Those are listed under "Public
blockers" below; each is a scope decision, not an accidental omission.

## Checklist

| # | Item | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Security review | documented | `docs/security-review.md` |
| 2 | Sandboxing review | documented | `docs/security-review.md` §4; `apps/worker/worker/sandbox/` |
| 3 | Privacy review | documented | `docs/privacy.md` |
| 4 | Abuse controls | partial | version gate, lease cap, quotas, duplicate verification — **no rate limiting** |
| 5 | Worker auto-update | partial | `MIN_WORKER_VERSION` gate + `--check-update`; **manual reinstall** |
| 6 | Credential revocation | present | `POST /workers/{id}/revoke`, `/rotate-credential` |
| 7 | Monitoring | present | `/health`, `/network/summary`, `/network/capacity`, `worker --diagnostics` |
| 8 | Incident handling | documented | `docs/incident-response.md` |
| 9 | Terms / privacy docs | documented | `docs/terms.md`, `docs/privacy.md` |
| 10 | Data retention policy | present | `docs/data-retention.md`, `app/services/retention.py`, `POST /beta/prune` |
| 11 | Customer isolation | present | `/api/v1` trust domain, `Job.isolation_scope` (Sprint 29/30) |

Every row is backed by a file, route, or test; `GET /beta/readiness` re-derives
the statuses from live state and returns `invited_beta: "go"`.

## Public blockers

These are the reasons public enrollment is NO-GO today. They are properties of
the prototype, not bugs:

1. **No TLS.** The coordinator serves plain HTTP; public traffic must be
   encrypted end-to-end.
2. **No real workloads.** Only deterministic stub workloads exist; no sandboxed
   AI runtime is bundled, and there is no network-isolated execution required
   for real workloads.
3. **Check-only updates.** Contributors would have to reinstall by hand.
4. **No rate limiting / abuse detection.**
5. **No cross-network proof.** Everything is proven on a trusted LAN; no
   public-internet contributor has joined.

`GET /beta/readiness` returns these as `decision.public_blockers` with
`met: false`; the public decision flips to `go` automatically when all are met.

## What "GO" for the invited beta actually means

- Enrollment is **operator-minted and single-use** (`POST /auth/enrollment-tokens`);
  there is no self-serve signup.
- Contributors are **known and trusted**, on a **trusted network**.
- Only **allowlisted workloads** run — currently deterministic pure-compute
  stubs. No arbitrary customer code.
- The operator watches `/network/*`, can `pause`/`revoke` at any time, and
  follows `docs/incident-response.md`.
- Retention is enforced deliberately (`scripts/prune.py`, dry-run first).

## Reproduce the decision

```powershell
python -m uvicorn app.main:app --app-dir apps/coordinator   # then:
#   GET http://127.0.0.1:8000/beta/readiness
python scripts/prune.py                                      # retention dry run
```

## Conditions to revisit

Re-run this review when any of the public blockers is removed. Public
enrollment should only open when `GET /beta/readiness` reports
`public_enrollment: "go"` **and** a cross-network contributor test has passed
(Sprint 36 scope).
