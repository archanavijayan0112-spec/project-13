"""Pydantic schemas for API request/response validation."""

from pydantic import BaseModel, HttpUrl, Field, field_validator
from typing import Any, Dict, List, Optional
from datetime import datetime
from app.models.db_models import JobStatus


# ─── Scrape Schemas ────────────────────────────────────────────────────────────

class ExtractionField(BaseModel):
    """Defines a single field to extract from a page."""
    name: str = Field(..., description="Field name in the output")
    description: str = Field(..., description="What this field contains (used by AI)")
    field_type: str = Field(default="string", description="string | number | boolean | list | object")
    required: bool = True
    example: Optional[str] = None


class ExtractionSchema(BaseModel):
    """User-defined schema telling AI what to extract."""
    fields: List[ExtractionField]
    instructions: Optional[str] = Field(None, description="Extra instructions for the AI extractor")


class ScrapeOptions(BaseModel):
    use_playwright: bool = Field(False, description="Use headless browser (for JS-heavy pages)")
    wait_for_selector: Optional[str] = Field(None, description="CSS selector to wait for before scraping")
    custom_headers: Optional[Dict[str, str]] = None
    follow_pagination: bool = Field(False, description="Auto-follow pagination links")
    max_pages: int = Field(5, ge=1, le=50, description="Max pages per URL when paginating")
    delay_seconds: float = Field(1.0, ge=0, le=10)


class SingleScrapeRequest(BaseModel):
    url: str = Field(..., description="URL to scrape")
    schema_def: Optional[ExtractionSchema] = Field(None, description="AI extraction schema")
    options: ScrapeOptions = Field(default_factory=ScrapeOptions)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class BatchScrapeRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1, max_length=100)
    schema_def: Optional[ExtractionSchema] = None
    options: ScrapeOptions = Field(default_factory=ScrapeOptions)

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v):
        for url in v:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Invalid URL: {url}")
        return v


# ─── Extract Schemas ───────────────────────────────────────────────────────────

class ExtractFromTextRequest(BaseModel):
    """Extract structured data from raw text or HTML."""
    content: str = Field(..., min_length=10, description="Raw text or HTML to extract from")
    schema_def: ExtractionSchema
    source_url: Optional[str] = None


# ─── Job Schemas ───────────────────────────────────────────────────────────────

class JobResponse(BaseModel):
    id: str
    url: Optional[str]
    status: JobStatus
    progress: int
    total_urls: int
    scraped_urls: int
    result_count: int
    error: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    export_path: Optional[str]

    class Config:
        from_attributes = True


class ScrapedResultResponse(BaseModel):
    id: str
    job_id: str
    url: str
    page_title: Optional[str]
    status_code: Optional[int]
    extracted_data: Optional[Dict[str, Any]]
    extraction_tokens_used: int
    scraped_at: datetime

    class Config:
        from_attributes = True


# ─── Export Schemas ────────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    job_id: str
    format: str = Field("json", description="json | csv | excel")

    @field_validator("format")
    @classmethod
    def validate_format(cls, v):
        if v not in ("json", "csv", "excel"):
            raise ValueError("Format must be json, csv, or excel")
        return v


# ─── Generic ───────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
    job_id: Optional[str] = None
