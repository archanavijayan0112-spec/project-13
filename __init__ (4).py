"""
Extraction API routes.
POST /api/v1/extract/       — extract structured data from raw text/HTML
POST /api/v1/extract/url    — scrape + extract in one call
"""

from fastapi import APIRouter, HTTPException
from app.models.schemas import ExtractFromTextRequest, SingleScrapeRequest, ScrapedResultResponse
from app.services.extractor import extractor_service
from app.services.scraper import scraper_service

router = APIRouter()


@router.post("/", summary="Extract structured data from raw HTML or text")
async def extract_from_text(request: ExtractFromTextRequest):
    """
    Pass raw HTML or text + a schema. AI extracts structured fields.
    No scraping needed — useful when you already have the content.
    """
    is_html = "<html" in request.content.lower() or "<body" in request.content.lower()
    extracted, tokens = await extractor_service.extract_with_fallback(
        request.content, request.schema_def, is_html=is_html
    )
    return {
        "source_url": request.source_url,
        "extracted": extracted,
        "tokens_used": tokens,
        "fields_extracted": len([v for v in extracted.values() if v is not None]),
        "fields_total": len(request.schema_def.fields),
    }


@router.post("/url", summary="Scrape a URL and extract structured data in one call")
async def extract_from_url(request: SingleScrapeRequest):
    """
    Combined scrape + AI extract endpoint.
    Requires a schema_def. Returns extracted structured data directly.
    """
    if not request.schema_def:
        raise HTTPException(status_code=400, detail="schema_def is required for this endpoint")

    try:
        page = await scraper_service.scrape_url(
            url=request.url,
            use_playwright=request.options.use_playwright,
            wait_for_selector=request.options.wait_for_selector,
            custom_headers=request.options.custom_headers,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scraping failed: {e}")

    extracted, tokens = await extractor_service.extract_with_fallback(
        page.html, request.schema_def
    )

    return {
        "url": page.url,
        "title": page.title,
        "status_code": page.status_code,
        "scrape_duration_ms": page.duration_ms,
        "extracted": extracted,
        "tokens_used": tokens,
    }
