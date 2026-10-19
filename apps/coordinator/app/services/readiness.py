"""Public-beta readiness (Sprint 35): the roadmap checklist as checkable data.

The sprint's exit condition is *a documented go/no-go decision for public
worker enrollment*. This module turns the 11-item checklist into a status
report sourced from live state (routes present, settings configured, review
docs on disk) rather than prose alone. `docs/public-beta-readiness.md` is the
human narrative; this is the machine-checkable mirror of it.

Status vocabulary (a closed set):

- ``present``     -- implemented and observable right now
- ``documented``  -- a process/policy/gap that is written down and followed
- ``partial``     -- implemented for a *trusted, invited* beta but not for the
                     open public internet
- ``gap``         -- not addressed; blocks any enrollment

The decision block is derived: public enrollment is a **go** only when every
public blocker is met; the invited-beta decision is a **go** when no checklist
item is a ``gap``. Today the prototype is deliberately NO-GO/GO.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

PRESENT = "present"
DOCUMENTED = "documented"
PARTIAL = "partial"
GAP = "gap"


def _repo_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file() and (parent / "docs").is_dir():
            return parent
    return None


def _review_root() -> Path | None:
    root = _repo_root()
    return (root / "docs") if root else None


def _has_doc(name: str) -> bool:
    docs = _review_root()
    return bool(docs and (docs / name).is_file())


def _has_dir(*parts: str) -> bool:
    root = _repo_root()
    return bool(root and (root.joinpath(*parts)).is_dir())


def _check(item: str, status: str, summary: str, evidence: list[str]) -> dict:
    return {"item": item, "status": status, "summary": summary, "evidence": evidence}


def collect_route_paths(routes) -> set[str]:
    """Flatten an app's routes to path strings, descending into included routers.

    Some Starlette builds keep an included router as a single wrapper object
    (`original_router`); handle both that and plain route objects.
    """
    paths: set[str] = set()
    for route in routes:
        path = getattr(route, "path", None)
        if path:
            paths.add(path)
        original = getattr(route, "original_router", None)
        if original is not None:
            paths |= collect_route_paths(original.routes)
    return paths


def build_readiness(
    *,
    version: str,
    settings,
    route_paths: set[str],
    now: datetime | None = None,
) -> dict:
    """Compose the checklist status + go/no-go decision from live state."""
    moment = now or datetime.now(timezone.utc)

    has_revoke = "/workers/{worker_id}/revoke" in route_paths
    has_rotate = "/workers/{worker_id}/rotate-credential" in route_paths
    monitoring_routes = {
        p for p in ("/health", "/network/summary", "/network/capacity") if p in route_paths
    }
    customer_api = any(p.startswith("/api/v1") for p in route_paths)

    retention = {
        "telemetry_days": getattr(settings, "retention_telemetry_days", None),
        "work_days": getattr(settings, "retention_work_days", None),
        "financial_days": getattr(settings, "retention_financial_days", None),
    }
    retention_enforced = bool(retention["telemetry_days"] and retention["work_days"])

    checks = [
        _check(
            "security_review", DOCUMENTED,
            "Threat model + controls reviewed in writing.",
            ["docs/security-review.md"],
        ),
        _check(
            "sandboxing_review",
            DOCUMENTED if _has_dir("apps", "worker", "worker", "sandbox") else GAP,
            "Worker executes allowlisted workloads with per-unit temp dirs; the "
            "Job Object sandbox child is available on Windows.",
            ["apps/worker/worker/sandbox/", "docs/security-review.md"],
        ),
        _check(
            "privacy_review",
            DOCUMENTED if _has_doc("privacy.md") else GAP,
            "Plain-language data-flow review; nothing leaves the machine but "
            "the hardware profile, heartbeats, and results.",
            ["docs/privacy.md"],
        ),
        _check(
            "abuse_controls", PARTIAL,
            "Version gate, per-worker lease cap, customer quotas, and duplicate "
            "verification exist; no API rate limiting or automated abuse "
            "detection yet.",
            [
                f"MIN_WORKER_VERSION={settings.min_worker_version or '(off)'}",
                f"MAX_LEASES_PER_WORKER={settings.max_leases_per_worker}",
                "customer quotas (Sprint 30)",
                "duplicate verification (Sprint 8)",
            ],
        ),
        _check(
            "worker_auto_update", PARTIAL,
            "Version gate blocks work from outdated workers; update is "
            "check-only -- contributors reinstall a fresh build.",
            ["GET /health version", "worker --check-update", "MIN_WORKER_VERSION"],
        ),
        _check(
            "credential_revocation",
            PRESENT if has_revoke else GAP,
            "Revoke all credentials for a worker, or rotate one credential "
            "without touching enrollment; revocation is enforced per request.",
            [
                "POST /workers/{id}/revoke",
                "POST /workers/{id}/rotate-credential" if has_rotate else "(rotate route not found)",
                "docs/beta.md",
            ],
        ),
        _check(
            "monitoring",
            PRESENT if len(monitoring_routes) == 3 else PARTIAL,
            "Liveness, fleet rollup, and capacity views; contributor diagnostics "
            "are redacted by construction.",
            sorted(monitoring_routes) + ["worker --diagnostics"],
        ),
        _check(
            "incident_handling",
            DOCUMENTED if _has_doc("incident-response.md") else GAP,
            "Written runbook: containment (revoke/pause), evidence, and "
            "notification.",
            ["docs/incident-response.md"],
        ),
        _check(
            "terms_privacy",
            DOCUMENTED if _has_doc("terms.md") and _has_doc("privacy.md") else GAP,
            "Participation terms + privacy notice for contributors.",
            ["docs/terms.md", "docs/privacy.md"],
        ),
        _check(
            "data_retention",
            PRESENT if (retention_enforced and _has_doc("data-retention.md")) else PARTIAL,
            "Documented retention windows with an operator-invoked enforcement "
            "path (dry-run by default).",
            ["docs/data-retention.md", "app/services/retention.py", "POST /beta/prune"],
        ),
        _check(
            "customer_isolation",
            PRESENT if customer_api else GAP,
            "Customer API is a separate trust domain; input/output access is "
            "scoped to the job's isolation_scope.",
            ["/api/v1", "isolation_scope (Sprint 30)", "docs/security-review.md"],
        ),
    ]

    # Public enrollment additionally requires the network to be safe on the
    # open internet -- none of these are true for the prototype.
    public_blockers = [
        {"item": "tls_enforced", "met": False,
         "detail": "The coordinator serves plain HTTP in the prototype; TLS is a "
                   "public-networking task, not a LAN one."},
        {"item": "real_workloads", "met": False,
         "detail": "Only deterministic stub workloads exist; no sandboxed AI "
                   "runtime is bundled."},
        {"item": "worker_auto_update", "met": False,
         "detail": "Update is check-only; public contributors would need to "
                   "reinstall by hand."},
        {"item": "rate_limiting", "met": False,
         "detail": "No API rate limiting or automated abuse detection."},
        {"item": "cross_network_e2e", "met": False,
         "detail": "Proven on a trusted LAN only; no public-internet "
                   "contributor test."},
    ]

    public_go = all(b["met"] for b in public_blockers)
    invited_go = all(c["status"] != GAP for c in checks)

    return {
        "version": version,
        "generated_at": moment.isoformat(),
        "checklist": checks,
        "retention": retention,
        "decision": {
            "public_enrollment": "go" if public_go else "no-go",
            "invited_beta": "go" if invited_go else "no-go",
            "rationale": (
                "Trusted, invited, technical contributors running allowlisted "
                "workloads on a trusted network are responsible today. Open "
                "public enrollment is not, because the public-internet "
                "requirements below are unmet."
                if invited_go and not public_go else
                "See checklist and blockers."
            ),
            "public_blockers": public_blockers,
        },
    }
