"""Public-beta readiness + maintenance endpoints (Sprint 35).

- `GET  /beta/readiness` -- the go/no-go checklist as live, checkable data.
- `POST /beta/prune`     -- enforce the retention policy. **Dry run by
  default** (`?apply=true` to actually delete). See `docs/data-retention.md`
  and `app/services/retention.py`.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.health import VERSION
from app.config import get_settings
from app.db import get_db
from app.services import retention
from app.services.readiness import build_readiness, collect_route_paths

router = APIRouter()


@router.get("/beta/readiness")
def beta_readiness(request: Request) -> dict:
    """Checklist status + documented go/no-go decision for public enrollment."""
    return build_readiness(
        version=VERSION,
        settings=get_settings(),
        route_paths=collect_route_paths(request.app.routes),
    )


@router.post("/beta/prune")
def beta_prune(
    telemetry_days: int | None = None,
    work_days: int | None = None,
    financial_days: int | None = None,
    apply: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    """Age out data older than the retention windows (dry run unless apply)."""
    settings = get_settings()
    return retention.prune(
        db,
        telemetry_days=(
            telemetry_days if telemetry_days is not None else settings.retention_telemetry_days
        ),
        work_days=work_days if work_days is not None else settings.retention_work_days,
        financial_days=(
            financial_days if financial_days is not None else settings.retention_financial_days
        ),
        apply=apply,
    )
