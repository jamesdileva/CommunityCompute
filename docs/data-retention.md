# Data Retention Policy (Sprint 35)

What the coordinator keeps, for how long, and how it is removed. The prototype
store is SQLite and disposable (AGENTS.md §7), but retention still needs an
explicit, enforced policy before contributors are trusted with their data.

## Windows

| Category | Default | What it covers |
| --- | --- | --- |
| **Telemetry** | 7 days | `worker_heartbeats`, `worker_resource_samples` — high-write diagnostics. |
| **Work** | 30 days | terminal work units + their `results` + `work_unit_attempts`, and used/expired `enrollment_tokens`. |
| **Financial** | keep forever (`0`) | `contribution_records` + `credit_ledger` — the audit/economics record. |

**Always retained** (small, needed for trust and operations): `workers`,
`worker_credentials` (revoked ones too, until the worker is deleted),
`jobs` summaries, and `reputation_events`.

## Rules

- Only **terminal** work units are ever eligible (completed/failed/cancelled/
  interrupted). A unit that is `queued`, `dispatched`, or `running` — i.e.
  holding a live lease — is never removed.
- Deletion cannot break accounting: neither `contribution_records` nor
  `credit_ledger` has a foreign key to `work_units`, so aging out unit
  artifacts never orphans a ledger row.
- Identity and credentials are never aged out by the pruner.
- Enforcement is **explicit and dry-run by default**. Nothing is deleted
  automatically; there is no background job.

## How to enforce

```powershell
python scripts/prune.py                    # dry run (default windows)
python scripts/prune.py --apply            # actually delete
python scripts/prune.py --work-days 14 --financial-days 180 --apply
# with the coordinator running (dry run unless apply=true):
#   POST /beta/prune
#   POST /beta/prune?apply=true
```

Windows are configured in `apps/coordinator/app/config.py`
(`RETENTION_TELEMETRY_DAYS`, `RETENTION_WORK_DAYS`,
`RETENTION_FINANCIAL_DAYS`) and reported by `GET /beta/readiness`.

## Recommended operating rhythm

- Run a **dry run weekly** and review the counts.
- **Apply** telemetry/work windows weekly; financial records only on a schedule
  you have deliberately chosen (default: never).
- Before any destructive prune, copy `communitycompute.db` to a dated backup.

## Open decisions (before public enrollment)

- Whether financial records should eventually expire (legal/tax) and after how
  long.
- Per-customer retention/deletion obligations once real customers exist.
- Encrypting backups and the database at rest.
