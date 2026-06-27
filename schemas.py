"""
Jobs API routes.
GET  /api/v1/jobs/              — list all jobs
GET  /api/v1/jobs/{id}          — get job status
GET  /api/v1/jobs/{id}/results  — get job results
POST /api/v1/jobs/{id}/export   — export results to file
DELETE /api/v1/jobs/{id}        — cancel/delete job
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
import os

from app.core.database import get_db
from app.models.db_models import ScrapeJob, ScrapedResult, JobStatus
from app.models.schemas import JobResponse, ScrapedResultResponse, ExportRequest, MessageResponse
from app.services.exporter import export_service

router = APIRouter()


@router.get("/", response_model=List[JobResponse], summary="List all scrape jobs")
async def list_jobs(
    limit: int = 20,
    offset: int = 0,
    status: str = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(ScrapeJob).order_by(ScrapeJob.created_at.desc()).limit(limit).offset(offset)
    if status:
        try:
            query = query.where(ScrapeJob.status == JobStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobResponse, summary="Get job status")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(ScrapeJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/results", response_model=List[ScrapedResultResponse], summary="Get job results")
async def get_job_results(
    job_id: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(ScrapeJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    query = (
        select(ScrapedResult)
        .where(ScrapedResult.job_id == job_id)
        .order_by(ScrapedResult.scraped_at)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/{job_id}/export", summary="Export job results to JSON / CSV / Excel")
async def export_job(job_id: str, request: ExportRequest, db: AsyncSession = Depends(get_db)):
    job = await db.get(ScrapeJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Job is not completed (status={job.status})")

    # Fetch all results
    query = select(ScrapedResult).where(ScrapedResult.job_id == job_id)
    result = await db.execute(query)
    results = result.scalars().all()

    if not results:
        raise HTTPException(status_code=404, detail="No results found for this job")

    # Export
    fmt = request.format
    if fmt == "json":
        path = export_service.export_json(job_id, results)
        media_type = "application/json"
        filename = f"scrape_{job_id}.json"
    elif fmt == "csv":
        path = export_service.export_csv(job_id, results)
        media_type = "text/csv"
        filename = f"scrape_{job_id}.csv"
    elif fmt == "excel":
        path = export_service.export_excel(job_id, results)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"scrape_{job_id}.xlsx"
    else:
        raise HTTPException(status_code=400, detail="Invalid format")

    # Update export path in DB
    job.export_path = path
    await db.commit()

    return FileResponse(path, media_type=media_type, filename=filename)


@router.delete("/{job_id}", response_model=MessageResponse, summary="Delete a job and its results")
async def delete_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(ScrapeJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Delete results
    query = select(ScrapedResult).where(ScrapedResult.job_id == job_id)
    result = await db.execute(query)
    for r in result.scalars().all():
        await db.delete(r)

    await db.delete(job)
    await db.commit()
    return MessageResponse(message=f"Job {job_id} and all results deleted")
