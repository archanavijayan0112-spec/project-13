"""
AI-powered data extraction engine.
Uses LangChain + OpenAI to extract structured data from raw HTML/text
based on user-defined schemas.
"""

from typing import Any, Dict, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough
from bs4 import BeautifulSoup
import json

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import ExtractionSchema

logger = get_logger(__name__)


EXTRACTION_SYSTEM_PROMPT = """You are an expert data extraction AI. Your job is to extract structured data from web page content.

You will be given:
1. A schema describing what fields to extract
2. The web page content (cleaned text)

Rules:
- Extract ONLY the fields defined in the schema
- Follow the field types strictly (string, number, boolean, list, object)
- If a field cannot be found, return null for optional fields or your best guess for required fields
- Return ONLY valid JSON matching the schema exactly — no markdown, no explanation
- For lists, return an array even if there's only one item
- For numbers, return numeric values, not strings

{extra_instructions}
"""

EXTRACTION_USER_PROMPT = """Schema to extract:
{schema}

Web page content:
---
{content}
---

Extract the data as a JSON object with keys matching the schema field names exactly."""


class AIExtractorService:
    """LangChain-powered structured data extraction from web content."""

    def __init__(self):
        self._llm: Optional[ChatOpenAI] = None

    def _get_llm(self) -> ChatOpenAI:
        if self._llm is None:
            if not settings.OPENAI_API_KEY:
                raise ValueError(
                    "OPENAI_API_KEY not set. Add it to your .env file."
                )
            self._llm = ChatOpenAI(
                model=settings.LLM_MODEL,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.MAX_TOKENS,
                openai_api_key=settings.OPENAI_API_KEY,
            )
        return self._llm

    def clean_html(self, html: str, max_chars: int = 12000) -> str:
        """Strip HTML tags and return clean readable text."""
        soup = BeautifulSoup(html, "html.parser")

        # Remove noise elements
        for tag in soup(["script", "style", "nav", "footer", "head", "noscript", "iframe"]):
            tag.decompose()

        # Get meaningful text
        text = soup.get_text(separator="\n", strip=True)

        # Collapse whitespace
        import re
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)

        # Truncate to avoid token limits
        if len(text) > max_chars:
            logger.warning(f"Content truncated from {len(text)} to {max_chars} chars")
            text = text[:max_chars] + "\n...[truncated]"

        return text.strip()

    def _build_schema_description(self, schema: ExtractionSchema) -> str:
        """Convert schema to a clear textual description for the LLM."""
        lines = []
        for field in schema.fields:
            req = "required" if field.required else "optional"
            line = f'- "{field.name}" ({field.field_type}, {req}): {field.description}'
            if field.example:
                line += f' [example: {field.example}]'
            lines.append(line)
        return "\n".join(lines)

    async def extract(
        self,
        content: str,
        schema: ExtractionSchema,
        is_html: bool = True,
    ) -> Dict[str, Any]:
        """
        Extract structured data from content using the AI.

        Args:
            content: Raw HTML or plain text
            schema: Extraction schema defining desired fields
            is_html: Whether content is HTML (will be cleaned) or plain text

        Returns:
            dict of extracted field values
        """
        llm = self._get_llm()

        clean_content = self.clean_html(content) if is_html else content
        schema_desc = self._build_schema_description(schema)
        extra = schema.instructions or ""

        prompt = ChatPromptTemplate.from_messages([
            ("system", EXTRACTION_SYSTEM_PROMPT),
            ("user", EXTRACTION_USER_PROMPT),
        ])

        parser = JsonOutputParser()

        chain = prompt | llm | parser

        logger.info(f"Running AI extraction for schema with {len(schema.fields)} fields")

        result = await chain.ainvoke({
            "extra_instructions": extra,
            "schema": schema_desc,
            "content": clean_content,
        })

        logger.info(f"Extraction complete: {list(result.keys())}")
        return result

    async def extract_with_fallback(
        self,
        content: str,
        schema: ExtractionSchema,
        is_html: bool = True,
    ) -> tuple[Dict[str, Any], int]:
        """
        Extract with error handling. Returns (data, tokens_used).
        Falls back to empty dict if extraction fails.
        """
        try:
            result = await self.extract(content, schema, is_html)
            # Estimate tokens (rough: 1 token ≈ 4 chars)
            tokens_used = len(content) // 4
            return result, tokens_used
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in extraction: {e}")
            return {field.name: None for field in schema.fields}, 0
        except Exception as e:
            logger.error(f"AI extraction failed: {e}")
            return {field.name: None for field in schema.fields}, 0

    def quick_extract_no_ai(self, html: str) -> Dict[str, Any]:
        """
        Fast rule-based extraction (no AI, no API key needed).
        Extracts common fields: title, meta description, links, images, headings.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Title
        title = soup.find("title")
        title_text = title.get_text(strip=True) if title else None

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        description = meta_desc.get("content", "").strip() if meta_desc else None

        # All headings
        headings = {
            f"h{i}": [h.get_text(strip=True) for h in soup.find_all(f"h{i}")]
            for i in range(1, 4)
        }

        # All links
        links = [
            {"text": a.get_text(strip=True), "href": a.get("href", "")}
            for a in soup.find_all("a", href=True)
            if a.get("href", "").startswith("http")
        ][:50]  # cap at 50

        # Images
        images = [
            {"src": img.get("src", ""), "alt": img.get("alt", "")}
            for img in soup.find_all("img", src=True)
        ][:20]

        # Open Graph tags
        og = {}
        for tag in soup.find_all("meta", property=lambda v: v and v.startswith("og:")):
            og[tag.get("property", "").replace("og:", "")] = tag.get("content", "")

        return {
            "title": title_text,
            "description": description,
            "headings": headings,
            "links": links,
            "images": images,
            "open_graph": og,
        }


# Singleton
extractor_service = AIExtractorService()
