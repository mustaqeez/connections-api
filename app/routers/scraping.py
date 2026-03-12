import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.models.connection import Connection
from app.models.scrape_job import ScrapeJob
from app.schemas.scrape import ScrapeJobOut, ScrapeStart
from app.services.scraper import run_scrape_individual, run_scrape_segment, get_events

router = APIRouter(prefix="/api/scraping", tags=["scraping"])


@router.post("/connection/{connection_id}", response_model=ScrapeStart)
async def scrape_connection(
    connection_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    conn = await db.get(Connection, connection_id)
    if not conn:
        raise HTTPException(404, "Connection not found")

    job = ScrapeJob(
        scope="individual",
        connection_id=connection_id,
        total_profiles=1,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(run_scrape_individual, job.id, connection_id)

    return ScrapeStart(
        job_id=job.id,
        status="pending",
        message=f"Scrape started for {conn.name}",
    )


@router.post("/segment/{segment}", response_model=ScrapeStart)
async def scrape_segment(
    segment: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Connection).where(Connection.segment == segment)
    )
    connections = result.scalars().all()
    if not connections:
        raise HTTPException(404, f"No connections in segment {segment}")

    job = ScrapeJob(
        scope="segment",
        segment=segment,
        total_profiles=len(connections),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(run_scrape_segment, job.id, segment)

    return ScrapeStart(
        job_id=job.id,
        status="pending",
        message=f"Scrape started for {len(connections)} profiles in {segment}",
    )


@router.get("/jobs", response_model=list[ScrapeJobOut])
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
):
    result = await db.execute(
        select(ScrapeJob).order_by(ScrapeJob.started_at.desc()).limit(limit)
    )
    return [ScrapeJobOut.model_validate(j) for j in result.scalars().all()]


@router.get("/jobs/{job_id}", response_model=ScrapeJobOut)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(ScrapeJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return ScrapeJobOut.model_validate(job)


@router.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """SSE endpoint for live scrape progress."""
    job = await db.get(ScrapeJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    async def event_generator() -> AsyncGenerator[dict, None]:
        cursor = 0
        while True:
            events = get_events(job_id, after=cursor)
            for event in events:
                yield {"event": event.get("type", "message"), "data": json.dumps(event)}
                cursor += 1
                if event.get("type") in ("completed", "error"):
                    return
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())
