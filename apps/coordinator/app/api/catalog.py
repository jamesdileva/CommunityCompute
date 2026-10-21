"""Public workload catalog (Sprint 36).

Contributor- and visitor-facing, read-only: what this network runs and the
contract each workload carries. Deliberately unauthenticated -- the catalog is
public information (the same manifests are served, signed, to customers at
`/api/v1/workloads`). The signature stays in the customer view; this view is
the human-readable contract a contributor needs before joining.
"""

from fastapi import APIRouter

from app.config import get_settings
from app.services import billing
from app.services import workloads as workload_service

router = APIRouter()


@router.get("/workloads")
def list_workloads() -> list[dict]:
    """The supported workload types, their params, and their requirements."""
    settings = get_settings()
    out: list[dict] = []
    for workload_type in sorted(workload_service.KNOWN_WORKLOAD_TYPES):
        manifest = workload_service.signed_manifest(
            workload_type, settings.workload_signing_key
        )
        if manifest is None:
            continue
        requirements = manifest.get("requirements", {}) or {}
        out.append({
            "name": manifest["name"],
            "version": manifest["version"],
            "description": manifest.get("description", ""),
            "params": manifest.get("params", {}),
            "requirements": requirements,
            "gpu": bool(requirements.get("gpu")),
            "price_cents_per_unit": billing.unit_price(manifest["name"]),
            "currency": billing.currency(),
        })
    return out
