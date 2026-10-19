# Participation Terms — CommunityCompute prototype (Sprint 35)

Plain-language terms for the **invited, allowlisted prototype beta**. They are
written for a small trusted group; they are not a consumer contract and carry
no legal warranty. By enrolling a machine you agree to the points below.

## 1. What you are contributing

Spare compute from a machine you own and control. The worker runs only
allowlisted, deterministic workloads in a per-unit temporary directory. It
never reads your files, never opens inbound network ports, and stops instantly
when you pause or quit it. See `docs/privacy.md`.

## 2. What you get

Internal **contribution credits** (non-cash). Credits record verified work and
can be spent submitting jobs on the network. They have **no monetary value**,
are not redeemable, and may be reset if the prototype is rebuilt.

## 3. What you must not do

- Run the worker on a machine you do not own or are not authorised to use.
- Attack, probe, or overload the coordinator or other contributors.
- Submit workloads that are not on the supported allowlist, or attempt to make
  the worker execute arbitrary code.
- Share your enrollment token or credential outside the intended machine.

## 4. Availability and changes

The prototype may be reset, taken offline, or changed at any time without
notice. Work in progress is best-effort; jobs are retried on failures but no
completion guarantee is offered. Credits and history may be lost on a rebuild.

## 5. Security expectations

Treat the worker as security-sensitive software: keep it updated to at least
the operator's minimum version (`worker --check-update`), and report anything
suspicious. If a machine is lost, tell the operator so the credential can be
revoked (`POST /workers/{id}/revoke`).

## 6. Data

The coordinator keeps the records described in `docs/privacy.md` and ages them
out per `docs/data-retention.md`. You can uninstall at any time with
`scripts/uninstall_worker.ps1`; ask the operator to revoke the server-side
credential as well.

## 7. No warranty

The prototype is provided "as is", without warranty of any kind. The operator
is not liable for damage, data loss, or loss of credits arising from
participation. Public enrollment is currently closed; the operator decides who
may join.
