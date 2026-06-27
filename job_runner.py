"""
Web scraping engine.
- Fast HTTP scraping via httpx for static pages
- Playwright headless browser for JS-rendered pages
- Retry logic, rate limiting, pagination support
"""

import asyncio
import time
from typing import Optional, Dict, Tuple
import httpx
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ScrapedPage:
    """Container for a scraped page's data."""
    def __init__(
        self,
        url: str,
        html: str,
        status_code: int,
        title: str = "",
        duration_ms: int = 0,
    ):
        self.url = url
        self.html = html
        self.status_code = status_code
        self.title = title
        self.duration_ms = duration_ms


class ScraperService:
    """Handles all web scraping operations."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": settings.USER_AGENT},
                follow_redirects=True,
                timeout=settings.DEFAULT_TIMEOUT,
            )
        return self._client

    async def scrape_url(
        self,
        url: str,
        use_playwright: bool = False,
        wait_for_selector: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        retries: int = None,
    ) -> ScrapedPage:
        """Scrape a single URL, with retry logic."""
        max_retries = retries or settings.MAX_RETRIES
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Scraping [{attempt}/{max_retries}]: {url}")
                start = time.monotonic()

                if use_playwright:
                    page = await self._scrape_with_playwright(url, wait_for_selector, custom_headers)
                else:
                    page = await self._scrape_with_httpx(url, custom_headers)

                page.duration_ms = int((time.monotonic() - start) * 1000)
                logger.info(f"Scraped {url} in {page.duration_ms}ms (status={page.status_code})")
                return page

            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt} failed for {url}: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(settings.RETRY_DELAY * attempt)

        raise RuntimeError(f"Failed to scrape {url} after {max_retries} attempts: {last_error}")

    async def _scrape_with_httpx(
        self,
        url: str,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> ScrapedPage:
        client = await self._get_client()
        headers = custom_headers or {}
        response = await client.get(url, headers=headers)
        html = response.text
        title = self._extract_title(html)
        return ScrapedPage(
            url=str(response.url),
            html=html,
            status_code=response.status_code,
            title=title,
        )

    async def _scrape_with_playwright(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> ScrapedPage:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError("Playwright not installed. Run: pip install playwright && playwright install")

        async with async_playwright() as pw:
            browser_type = getattr(pw, settings.PLAYWRIGHT_BROWSER)
            browser = await browser_type.launch(headless=settings.PLAYWRIGHT_HEADLESS)
            context = await browser.new_context(
                user_agent=settings.USER_AGENT,
                extra_http_headers=custom_headers or {},
            )
            page = await context.new_page()

            response = await page.goto(url, timeout=settings.DEFAULT_TIMEOUT * 1000)

            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=10000)
            else:
                await page.wait_for_load_state("networkidle", timeout=15000)

            html = await page.content()
            title = await page.title()
            status_code = response.status if response else 200

            await browser.close()
            return ScrapedPage(url=url, html=html, status_code=status_code, title=title)

    async def scrape_with_pagination(
        self,
        url: str,
        use_playwright: bool = False,
        max_pages: int = 5,
        delay: float = 1.0,
    ) -> list[ScrapedPage]:
        """Follow pagination links and collect all pages."""
        pages = []
        current_url = url
        visited = set()

        for page_num in range(1, max_pages + 1):
            if current_url in visited:
                break
            visited.add(current_url)

            page = await self.scrape_url(current_url, use_playwright=use_playwright)
            pages.append(page)
            logger.info(f"Pagination: scraped page {page_num}/{max_pages}")

            next_url = self._find_next_page(page.html, current_url)
            if not next_url:
                logger.info("No more pagination links found.")
                break

            current_url = next_url
            await asyncio.sleep(delay)

        return pages

    def _extract_title(self, html: str) -> str:
        import re
        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else ""

    def _find_next_page(self, html: str, base_url: str) -> Optional[str]:
        """Find the 'next page' link in HTML."""
        import re
        from urllib.parse import urljoin, urlparse

        # Common patterns: rel="next", text="Next", aria-label="Next page"
        patterns = [
            r'<a[^>]+rel=["\']next["\'][^>]*href=["\']([^"\']+)["\']',
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']next["\']',
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*(?:Next|next|›|»|→)\s*</a>',
            r'<a[^>]*class="[^"]*next[^"]*"[^>]*href=["\']([^"\']+)["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                href = match.group(1)
                if href.startswith("http"):
                    return href
                return urljoin(base_url, href)
        return None

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Singleton
scraper_service = ScraperService()
