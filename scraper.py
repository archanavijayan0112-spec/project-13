"""
AI Web Scraper + Data Extractor
FastAPI + LangChain powered intelligent scraping engine
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import uvicorn

from app.api.routes import scrape, extract, jobs, health
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    from app.core.database import init_db
    await init_db()
    yield


app = FastAPI(
    title="AI Web Scraper & Data Extractor",
    description="""
    🤖 **AI-powered web scraping and data extraction API**

    Features:
    - Intelligent scraping with Playwright (handles JS-rendered pages)
    - LangChain-powered AI extraction with structured output
    - Async job queue for large-scale scraping
    - Rate limiting and retry logic
    - Export to JSON, CSV, Excel
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, tags=["Health"])
app.include_router(scrape.router, prefix="/api/v1/scrape", tags=["Scrape"])
app.include_router(extract.router, prefix="/api/v1/extract", tags=["Extract"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=settings.WORKERS,
    )
