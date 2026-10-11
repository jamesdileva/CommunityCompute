"""Jobs API (Sprint 5 submit/status; Sprint 10: compatibility explanation)."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.capability import WorkerCapability
from app.models.job import Job
from app.schemas.job import JobCreate, JobOut, JobStatusOut, WorkUnitOut
from app.services import jobs as job_service
from app.services import work as work_service
from app.services.explain import explain

log = logging.getLogger("coordinator")

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobOut, status_code=201)
def submit_job(payload: JobCreate, db: Session = Depends(get_db)) -> JobOut:
    job, units = job_service.create_job(db, payload)
    log.info(
        "job created id=%s type=%s total=%d chunk=%d units=%d",
        job.id, job.workload_type, job.total_units, job.chunk_size, len(units),
    )
    return JobOut.model_validate(job)


@router.get("", response_model=list[JobOut])
def list_jobs(db: Session = Depends(get_db)) -> list[JobOut]:
    return [JobOut.model_validate(j) for j in job_service.list_jobs(db)]


@router.get("/{job_id}/compatibility/{worker_id}")
def job_compatibility(job_id: str, worker_id: str, db: Session = Depends(get_db)) -> dict:
    """Explain why this job's requirements do/don't fit this worker (Sprint 10)."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "unknown job"})
    cap = db.get(WorkerCapability, worker_id)
    if cap is None:
        raise HTTPException(status_code=404, detail={"error": "unknown worker (no capabilities)"})
    return explain(job.requirements, cap.profile)


@router.get("/{job_id}", response_model=JobStatusOut)
def job_status(job_id: str, db: Session = Depends(get_db)) -> JobStatusOut:
    data = job_service.job_status(db, job_id)
    if data is None:
        raise HTTPException(status_code=404, detail={"error": "unknown job"})
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
