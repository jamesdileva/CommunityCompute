# Support & troubleshooting (participants)

Plain-language help for contributors. Everything here is safe to run — none of
it reveals your credential.

## First, collect a diagnostic bundle

```powershell
worker --diagnostics
```

This prints a redacted support bundle: identity (id and status, **not** the
secret), worker/coordinator versions, your policy, detected capabilities,
sandbox availability, and a log tail. Send this output to the operator when you
ask for help. It never includes your bearer credential or your files.

Start with the one-screen status:

```powershell
worker --status
```

It tells you whether you are reachable, enrolled, within policy, and eligible
for work right now.

## Common issues

### "register REJECTED (401) — re-enroll"
Your credential is invalid or was revoked (for example after a rotate). Get a
**fresh** enrollment token from the operator and run
`worker --enroll <token> --coordinator-url http://<coordinator>:8000`, then
start again.

### "Coordinator unreachable" / connection refused
- Confirm the coordinator URL (`--coordinator-url`), including the port.
- Confirm the coordinator is running and on the same LAN.
- The worker only makes **outbound** connections, so no firewall change is
  needed on your side; a blocked outbound connection is the usual cause.

### The worker runs, but I never receive work
This is normal early in a beta — the queue may simply be empty. If it persists:
- `worker --status` may say you are outside your allowed hours, on battery with
  `plugged_only`, above the temperature ceiling, or above your CPU/GPU cap;
- your machine may be too small for the currently queued workload requirements;
- check the **Network** tab (operator view) to see whether units are queued.

### I want to contribute less (or only when idle)
Edit `policy.json` (its path is printed by `--setup`), or re-run
`worker --setup`. Changes apply within one worker tick. Lowering
`max_cpu_percent` / `max_gpu_percent`, setting `idle_only`, a temperature
ceiling, or allowed hours all reduce impact.

### My credit balance is not going up
Credit is awarded **only for verified work units**. If you are idle, outside
policy hours, or your results are being rejected during verification, the
balance stays flat. Check the **My node** dashboard tab for `rejected` /
`expired` counts and current work. A prototype balance has **no cash value**.

### Auto-start does not work
Re-run `worker --install-autostart` (or remove it with
`worker --remove-autostart` and re-add). Auto-start registers a login entry; it
does not require administrator rights.

### Is my version current?
```powershell
worker --check-update
```
Updates are **checked, not pushed** in this beta: if you are behind, download
the current bundle and replace the binary.

### How do I stop / uninstall?
```powershell
worker --pause            # stop taking new work
worker --remove-autostart  # stop launching at login
```
Then remove the worker binary, its id/credential file, and `policy.json`. Ask
the operator to `POST /workers/{id}/revoke` to invalidate the credential server
side. See `docs/data-retention.md` and `docs/privacy.md`.

## For the operator

- Mint an enrollment token: `POST /auth/enrollment-tokens`
  `{"note": "<who/which machine>"}` (returns the token once; stores a hash).
- Inspect tokens: `GET /auth/enrollment-tokens` (shows `used` / `used_by`).
- Revoke a machine: `POST /workers/{id}/revoke`; rotate: `POST /workers/{id}/rotate-credential`.
- Beta posture and known blockers: `docs/public-beta-readiness.md`.
- Security review and incident runbook: `docs/security-review.md`,
  `docs/incident-response.md`.
- Retention / pruning: `GET /beta/readiness`, `POST /beta/prune` (dry-run by
  default), or `python scripts/prune.py`.

## Reporting a problem

Send the operator the `worker --diagnostics` output, the exact command you ran,
and what you expected versus saw. For security issues, follow
`docs/security-review.md` rather than opening a public issue.
