"""
Async job runner for batch scraping operations.
Manages concurrency, progress tracking, and database updates.
"""

import asyncio
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.db_models import ScrapeJob, ScrapedResult, JobStatus
from app.models.schemas import ExtractionSchema, ScrapeOptions
from app.services.scraper import scraper_service
from app.services.extractor import extractor_service

logger = get_logger(__name__)

# Semaphore to cap concurrent scrapes globally
_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_SCRAPES)


async def run_scrape_job(job_id: str):
    """
    Background task: execute a scrape job end-to-end.
    Reads job config from DB, scrapes URLs, extracts data, saves results.
    """
    async with AsyncSessionLocal() as db:
        job = await db.get(ScrapeJob, job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        # Mark as running
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info(f"Job {job_id} started")

        try:
            urls: List[str] = job.urls or [job.url]
            job.total_urls = len(urls)
            await db.commit()

            schema: Optional[ExtractionSchema] = (
                ExtractionSchema(**job.schema_def) if job.schema_def else None
            )
            options = ScrapeOptions(
                use_playwright=bool(job.use_playwright),
                wait_for_selector=job.wait_for_selector,
                custom_headers=job.custom_headers,
                follow_pagination=bool(job.follow_pagination),
                max_pages=job.max_pages,
            )

            # Process URLs with concurrency control
            tasks = [
                _process_single_url(db, job, url, schema, options)
                for url in urls
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

            # Finalize job
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.duration_seconds = (
                job.completed_at - job.started_at
            ).total_seconds()
            job.progress = 100
            await db.commit()
            logger.info(f"Job {job_id} completed — {job.result_count} results")

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)


async def _process_single_url(
    db: AsyncSession,
    job: ScrapeJob,
    url: str,
    schema: Optional[ExtractionSchema],
    options: ScrapeOptions,
):
    """Process one URL: scrape + extract + save result."""
    async with _semaphore:
        try:
            # Polite delay
            await asyncio.sleep(options.delay_seconds)

            # Scrape
            if options.follow_pagination:
                pages = await scraper_service.scrape_with_pagination(
                    url,
                    use_playwright=options.use_playwright,
                    max_pages=options.max_pages,
                    delay=options.delay_seconds,
                )
            else:
                pages = [await scraper_service.scrape_url(
                    url,
                    use_playwright=options.use_playwright,
                    wait_for_selector=options.wait_for_selector,
                    custom_headers=options.custom_headers,
                )]

            for page in pages:
                # Extract
                if schema:
                    extracted, tokens = await extractor_service.extract_with_fallback(
                        page.html, schema, is_html=True
                    )
                else:
                    extracted = extractor_service.quick_extract_no_ai(page.html)
                    tokens = 0

                # Save result
                result = ScrapedResult(
                    job_id=job.id,
                    url=page.url,
                    raw_html=page.html[:50000],  # cap stored HTML
                    page_title=page.title,
                    status_code=page.status_code,
                    extracted_data=extracted,
                    extraction_tokens_used=tokens,
                    extraction_model=settings.LLM_MODEL if schema else "rule-based",
                    scrape_duration_ms=page.duration_ms,
                )
                db.add(result)

            job.scraped_urls += 1
            job.result_count += len(pages)
            job.progress = int((job.scraped_urls / job.total_urls) * 100)
            await db.commit()

        except Exception as e:
            logger.error(f"Failed to process {url}: {e}")
            # Save error result so the job continues
            error_result = ScrapedResult(
                job_id=job.id,
                url=url,
                extracted_data={"error": str(e)},
                status_code=0,
            )
            db.add(error_result)
            job.scraped_urls += 1
            job.progress = int((job.scraped_urls / job.total_urls) * 100)
            await db.commit()
