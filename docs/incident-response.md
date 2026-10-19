# Incident Response (Sprint 35)

How the operator contains, records, and closes an incident during the
invited beta. Kept deliberately short: the prototype has one operator (you), a
small number of known contributors, and a trusted network.

## Severities

| Level | Example | Target response |
| --- | --- | --- |
| **S1** | Coordinator down; data loss; credential/system compromise | Immediate containment, notify contributors. |
| **S2** | One worker misbehaving/compromised; job corruption; abuse | Contain within the day, document. |
| **S3** | Degraded throughput; single failed job; support request | Normal backlog. |

## Roles

- **Operator (on-call)**: makes containment calls, runs the commands below.
- **Contributor**: reports problems via `worker --diagnostics` output; can
  pause/quit locally at any time.
- There is no separate security team in the prototype; the operator is also
  the responder.

## Containment playbook

**Misbehaving or compromised worker** (S2)

```powershell
# Freeze it first (keeps identity + audit trail), then decide.
#   POST /workers/{id}/pause
# Revoke every credential it holds — the bearer dies on its next request.
#   POST /workers/{id}/revoke
# Rotate a single credential without losing enrollment:
#   POST /workers/{id}/rotate-credential
```

Then inspect what it did: `GET /workers/{id}/reputation`,
`GET /workers/{id}/stats`, `GET /accounting/entries?worker_id={id}`,
`GET /credits/ledger?worker_id={id}`. Verification overturns are recorded as
`voided_at` on `contribution_records`; fraudulent credits are neutralised by
voiding the records rather than editing the append-only ledger.

**Leaked customer key** (S2)

```
POST /api/v1/customers/{id}/revoke        # all keys
# or rotate a single key without touching the customer
```

**Bad workload definition / forged assignment** (S1 if confirmed)

Rotate `WORKLOAD_SIGNING_KEY` (coordinator) and redeploy the worker with the
matching key; in-flight assignments sealed with the old key stop being
accepted. Review `packages/protocol/workloads.py` and the signed-definition
history before re-enabling.

**Coordinator down / database corruption** (S1)

```
scripts/prune.py --apply          # never --apply blindly during an incident without a backup
# stop, back up communitycompute.db, then restart:
python -m uvicorn app.main:app --app-dir apps/coordinator
```

The prototype store is disposable (AGENTS.md); a corrupted dev DB is deleted
and rebuilt rather than repaired. Announce a maintenance window.

**Runaway load / suspected DoS** (S2)

There is **no rate limiting yet** (a known public-beta gap). Contain by
pausing workers (`POST /workers/{id}/pause`), lowering `MAX_LEASES_PER_WORKER`,
or taking the coordinator offline until the source is understood.

## Evidence to capture

- Timestamps (UTC) of detection and each action.
- Affected worker/customer ids and the commands run.
- `worker --diagnostics` output from the contributor (redacted by construction).
- Relevant coordinator log lines and the `reputation_events` / accounting rows.

## Notification

- **Contributors**: sent over the same trusted channel used for enrollment.
  Say what happened, what was contained, and whether they need to act
  (usually: nothing, or re-enroll if their credential was revoked).
- **Customers**: only if their scoped data or job results were affected.

## Post-incident

1. Write a dated entry in `worklog.md`: detection, impact, containment,
   root cause, and follow-up.
2. Add a regression test where the incident was preventable in code.
3. If it changes the threat model, update
   `docs/security-review.md` and re-check `docs/public-beta-readiness.md`.
