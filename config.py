"""
Scraping API routes.
POST /api/v1/scrape/        — single URL scrape (sync, instant)
POST /api/v1/scrape/batch   — batch URLs (async job)
POST /api/v1/scrape/quick   — scrape without AI (rule-based extraction)
"""

import asyncio
from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.core.database import get_db
from app.models.schemas import SingleScrapeRequest, BatchScrapeRequest, MessageResponse, ScrapedResultResponse
from app.models.db_models import ScrapeJob, ScrapedResult
from app.services.scraper import scraper_service
from app.services.extractor import extractor_service
from app.services.job_runner import run_scrape_job

router = APIRouter()


@router.post("/", response_model=ScrapedResultResponse, summary="Scrape a single URL (sync)")
async def scrape_single(request: SingleScrapeRequest, db: AsyncSession = Depends(get_db)):
    """
    Scrape a single URL and optionally extract structured data with AI.
    Returns immediately with results.
    """
    try:
        page = await scraper_service.scrape_url(
            url=request.url,
            use_playwright=request.options.use_playwright,
            wait_for_selector=request.options.wait_for_selector,
            custom_headers=request.options.custom_headers,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scraping failed: {e}")

    # Extract
    if request.schema_def:
        extracted, tokens = await extractor_service.extract_with_fallback(
            page.html, request.schema_def
        )
        model = "ai"
    else:
        extracted = extractor_service.quick_extract_no_ai(page.html)
        tokens = 0
        model = "rule-based"

    # Save to DB
    result = ScrapedResult(
        job_id="adhoc",
        url=page.url,
        raw_html=page.html[:50000],
        page_title=page.title,
        status_code=page.status_code,
        extracted_data=extracted,
        extraction_tokens_used=tokens,
        extraction_model=model,
        scrape_duration_ms=page.duration_ms,
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    return result


@router.post("/batch", response_model=MessageResponse, summary="Scrape multiple URLs (async job)")
async def scrape_batch(
    request: BatchScrapeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a batch of URLs for async scraping.
    Returns a job_id to track progress via GET /api/v1/jobs/{job_id}.
    """
    job = ScrapeJob(
        url=request.urls[0],
        urls=request.urls,
        schema_def=request.schema_def.model_dump() if request.schema_def else None,
        use_playwright=int(request.options.use_playwright),
        wait_for_selector=request.options.wait_for_selector,
        custom_headers=request.options.custom_headers,
        follow_pagination=int(request.options.follow_pagination),
        max_pages=request.options.max_pages,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(run_scrape_job, job.id)
    return MessageResponse(message=f"Batch job queued with {len(request.urls)} URLs", job_id=job.id)


@router.post("/quick", summary="Quick scrape — no AI, rule-based extraction only")
async def scrape_quick(url: str):
    """Fast scrape with rule-based extraction. No API key needed."""
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL")
    page = await scraper_service.scrape_url(url)
    extracted = extractor_service.quick_extract_no_ai(page.html)
    return {
        "url": page.url,
        "title": page.title,
        "status_code": page.status_code,
        "duration_ms": page.duration_ms,
        "extracted": extracted,
    }
