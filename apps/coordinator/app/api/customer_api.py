"""Customer API (Sprint 29): programmatic compute access at ``/api/v1``.

Exit condition this satisfies: *a separate test client can submit a supported
workload without using the dashboard.*

Two audiences, one namespace:

- **Operator** (unauthenticated in the prototype, exactly like Sprint 20's
  enrollment-token minting): create/list customers and rotate/revoke keys.
  Hardening arrives with Sprint 30's customer identity work.
- **Customer** (requires a valid API key as ``Authorization: Bearer``): submit
  jobs, poll status, fetch results, read usage. A customer only ever sees jobs
  it owns; anything else is a 404 (no existence leak).

Customer jobs run in the free community pool (architecture §21): no credits
are charged, so they carry no ``submitter_worker_id``.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import extract_bearer
from app.db import get_db
from app.models.customer import Customer
from app.models.result import Result
from app.schemas.customer import (
    CustomerCreate,
    CustomerCreated,
    CustomerJobRequest,
    CustomerKeyOut,
    CustomerOut,
    JobAccepted,
    JobResultsOut,
    JobResultUnit,
    RevokeCustomerResponse,
    RotateKeyResponse,
    UsageOut,
)
from app.schemas.job import JobCreate, JobStatusOut, WorkUnitOut
from app.services import customers as customer_service
from app.services import jobs as job_service
from app.services import work as work_service
from app.services.ws_registry import registry

log = logging.getLogger("coordinator")

router = APIRouter(prefix="/api/v1", tags=["customer-api"])


def require_customer(request: Request, db: Session = Depends(get_db)) -> Customer:
    """Authenticated customer from the bearer API key, or 401 (fails closed)."""
    customer = customer_service.verify_key(db, extract_bearer(request))
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "valid customer API key required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return customer


# ---- operator: customer + key management -------------------------------------


@router.post("/customers", response_model=CustomerCreated, status_code=201)
def create_customer(
    payload: CustomerCreate, db: Session = Depends(get_db)
) -> CustomerCreated:
    """Mint a customer + first API key. The raw key is returned exactly once."""
    customer, raw = customer_service.create_customer(db, name=payload.name, label=payload.label)
    log.info("customer created id=%s name=%s", customer.id, customer.name)
    return CustomerCreated(id=customer.id, name=customer.name, api_key=raw)


@router.get("/customers", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db)) -> list[CustomerOut]:
    return [CustomerOut(**row) for row in customer_service.list_customers(db)]


@router.get("/keys", response_model=list[CustomerKeyOut])
def list_keys(db: Session = Depends(get_db)) -> list[CustomerKeyOut]:
    """Non-secret view of every API key (prefixes only, never hashes)."""
    return [CustomerKeyOut(**row) for row in customer_service.list_keys(db)]


@router.get("/customers/{customer_id}/keys", response_model=list[CustomerKeyOut])
def list_customer_keys(customer_id: str, db: Session = Depends(get_db)) -> list[CustomerKeyOut]:
    return [CustomerKeyOut(**row) for row in customer_service.list_keys(db, customer_id)]


@router.post("/customers/{customer_id}/rotate-key", response_model=RotateKeyResponse)
def rotate_key(customer_id: str, db: Session = Depends(get_db)) -> RotateKeyResponse:
    """Issue a fresh key; the previous one is revoked immediately."""
    ok, reason, raw = customer_service.rotate_key(db, customer_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": reason})
    log.info("customer key rotated id=%s", customer_id)
    return RotateKeyResponse(customer_id=customer_id, api_key=raw or "", status="rotated")


@router.post("/customers/{customer_id}/revoke", response_model=RevokeCustomerResponse)
def revoke_customer(customer_id: str, db: Session = Depends(get_db)) -> RevokeCustomerResponse:
    """Revoke every active key for a customer."""
    ok, reason, count = customer_service.revoke_customer(db, customer_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": reason})
    log.info("customer keys revoked id=%s count=%d", customer_id, count)
    return RevokeCustomerResponse(customer_id=customer_id, revoked=count, status="revoked")


# ---- customer: jobs + usage --------------------------------------------------


@router.post("/jobs", response_model=JobAccepted, status_code=201)
def submit_job(
    payload: CustomerJobRequest,
    customer: Customer = Depends(require_customer),
    db: Session = Depends(get_db),
) -> JobAccepted:
    """Submit a job for this customer (free community pool — no credits charged)."""
    job, units = job_service.create_job(
        db,
        JobCreate(
            workload_type=payload.workload_type,
            params=payload.params,
            total_units=payload.total_units,
            chunk_size=payload.chunk_size,
            verify_sample=payload.verify_sample,
            requirements=payload.requirements,
        ),
        customer_id=customer.id,
    )
    log.info("customer job created id=%s customer=%s units=%d",
             job.id, customer.id, len(units))
    registry.broadcast_from_thread({"type": "work_available", "job_id": job.id})
    return JobAccepted(id=job.id, status=job.status, workload_type=job.workload_type,
                       total_units=job.total_units)


@router.get("/jobs/{job_id}", response_model=JobStatusOut)
def job_status(
    job_id: str,
    customer: Customer = Depends(require_customer),
    db: Session = Depends(get_db),
) -> JobStatusOut:
    if customer_service.owns_job(db, customer.id, job_id) is None:
        raise HTTPException(status_code=404, detail={"error": "unknown job"})
    data = job_service.job_status(db, job_id)
    assert data is not None  # ownership already confirmed it exists
    return JobStatusOut(
        id=data.job.id,
        workload_type=data.job.workload_type,
        params=data.job.params,
        total_units=data.job.total_units,
        chunk_size=data.job.chunk_size,
        status=data.job.status,
        verify_sample=data.job.verify_sample or 0.0,
        requirements=dict(data.job.requirements or {}),
        created_at=data.job.created_at,
        updated_at=data.job.updated_at,
        work_units=[WorkUnitOut.model_validate(u) for u in data.units],
        counts=data.counts,
        aggregate=work_service.aggregate_job(db, job_id),
    )


@router.get("/jobs/{job_id}/results", response_model=JobResultsOut)
def job_results(
    job_id: str,
    customer: Customer = Depends(require_customer),
    db: Session = Depends(get_db),
) -> JobResultsOut:
    """Per-unit results + aggregate for a job this customer owns."""
    if customer_service.owns_job(db, customer.id, job_id) is None:
        raise HTTPException(status_code=404, detail={"error": "unknown job"})
    data = job_service.job_status(db, job_id)
    assert data is not None
    results: list[JobResultUnit] = []
    for unit in data.units:
        row = db.get(Result, unit.id)
        results.append(
            JobResultUnit(
                work_unit_id=unit.id,
                sequence=unit.sequence,
                range_start=unit.range_start,
                range_end=unit.range_end,
                status=unit.status,
                ok=row.ok if row else None,
                value=row.value if row else None,
                output_hash=row.output_hash if row else None,
                execution_ms=row.execution_ms if row else None,
                verified_by=row.verified_by if row else None,
                failure_kind=row.failure_kind if row else None,
            )
        )
    return JobResultsOut(
        job_id=job_id,
        status=data.job.status,
        total_units=data.job.total_units,
        counts=data.counts,
        aggregate=work_service.aggregate_job(db, job_id),
        results=results,
    )


@router.get("/usage", response_model=UsageOut)
def usage(
    customer: Customer = Depends(require_customer), db: Session = Depends(get_db)
) -> UsageOut:
    """Read-only usage accounting for the authenticated customer."""
    return UsageOut(**customer_service.usage(db, customer.id))
