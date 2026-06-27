# project-13
AI Web Scraper# 🤖 AI Web Scraper & Data Extractor

A production-ready, AI-powered web scraping and structured data extraction API built with **FastAPI**, **LangChain**, and **Playwright**.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)
![LangChain](https://img.shields.io/badge/LangChain-0.3-orange.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

---

## ✨ Features

| Feature | Description |
|---|---|
| 🌐 **Smart Scraping** | httpx for static pages, Playwright for JS-heavy sites |
| 🧠 **AI Extraction** | LangChain + GPT-4o-mini extracts structured fields from any page |
| ⚡ **Async Batch Jobs** | Scrape 100s of URLs concurrently with job tracking |
| 🔄 **Pagination** | Auto-follows `Next` links across multi-page results |
| 📦 **Export** | Download results as JSON, CSV, or Excel |
| 🔁 **Retry Logic** | Exponential backoff on failures |
| 🐳 **Docker Ready** | One-command deploy with docker-compose |
| 📖 **Auto Docs** | Swagger UI at `/docs`, ReDoc at `/redoc` |

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/yourname/ai-web-scraper.git
cd ai-web-scraper

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY
```

### 3. Run

```bash
uvicorn app.main:app --reload
```

API is live at **http://localhost:8000**
Swagger docs at **http://localhost:8000/docs**

---

## 🐳 Docker Deploy

```bash
# Set your OpenAI key
export OPENAI_API_KEY=sk-...

# Start full stack (API + PostgreSQL + Redis)
docker-compose up -d
```

---

## 📡 API Reference

### Quick Scrape (no AI, instant)

```bash
curl "http://localhost:8000/api/v1/scrape/quick?url=https://news.ycombinator.com"
```

**Response:**
```json
{
  "url": "https://news.ycombinator.com",
  "title": "Hacker News",
  "status_code": 200,
  "extracted": {
    "title": "Hacker News",
    "headings": { "h1": ["Hacker News"] },
    "links": [...],
    "images": [...]
  }
}
```

---

### AI Scrape + Extract (structured data)

```bash
curl -X POST http://localhost:8000/api/v1/scrape/ \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
    "schema_def": {
      "fields": [
        {"name": "title",       "description": "Book title",           "field_type": "string"},
        {"name": "price",       "description": "Price with currency",  "field_type": "string"},
        {"name": "rating",      "description": "Star rating (1-5)",    "field_type": "number"},
        {"name": "in_stock",    "description": "Whether in stock",     "field_type": "boolean"},
        {"name": "description", "description": "Book synopsis",        "field_type": "string"}
      ]
    }
  }'
```

**Response:**
```json
{
  "url": "https://books.toscrape.com/...",
  "page_title": "A Light in the Attic",
  "extracted_data": {
    "title": "A Light in the Attic",
    "price": "£51.77",
    "rating": 3,
    "in_stock": true,
    "description": "It's hard to imagine a world without ..."
  }
}
```

---

### Batch Scrape (async job)

```bash
# Submit batch job
curl -X POST http://localhost:8000/api/v1/scrape/batch \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      "https://example.com/page1",
      "https://example.com/page2",
      "https://example.com/page3"
    ],
    "schema_def": {
      "fields": [
        {"name": "headline", "description": "Main headline", "field_type": "string"},
        {"name": "author",   "description": "Author name",   "field_type": "string"}
      ]
    },
    "options": { "use_playwright": false, "delay_seconds": 1.0 }
  }'

# Response: { "job_id": "abc-123", "message": "Batch job queued with 3 URLs" }

# Poll job status
curl http://localhost:8000/api/v1/jobs/abc-123

# Get results
curl http://localhost:8000/api/v1/jobs/abc-123/results
```

---

### Export Results

```bash
# Export to CSV
curl -X POST http://localhost:8000/api/v1/jobs/abc-123/export \
  -H "Content-Type: application/json" \
  -d '{"job_id": "abc-123", "format": "csv"}' \
  --output results.csv

# Export to Excel
curl -X POST http://localhost:8000/api/v1/jobs/abc-123/export \
  -H "Content-Type: application/json" \
  -d '{"job_id": "abc-123", "format": "excel"}' \
  --output results.xlsx
```

---

### Extract from Raw Text

```bash
curl -X POST http://localhost:8000/api/v1/extract/ \
  -H "Content-Type: application/json" \
  -d '{
    "content": "<p>Apple iPhone 15 Pro — $999 — Available in Black Titanium</p>",
    "schema_def": {
      "fields": [
        {"name": "product",  "description": "Product name",  "field_type": "string"},
        {"name": "price",    "description": "Price in USD",  "field_type": "string"},
        {"name": "color",    "description": "Color variant", "field_type": "string"}
      ]
    }
  }'
```

---

## 🧩 Scraping Options

| Option | Type | Default | Description |
|---|---|---|---|
| `use_playwright` | bool | `false` | Use headless browser for JS pages |
| `wait_for_selector` | string | `null` | CSS selector to wait for |
| `custom_headers` | object | `null` | Extra request headers |
| `follow_pagination` | bool | `false` | Auto-follow Next page links |
| `max_pages` | int | `5` | Max pages when paginating |
| `delay_seconds` | float | `1.0` | Polite delay between requests |

---

## 🗂 Project Structure

```
ai-web-scraper/
├── app/
│   ├── main.py                  # FastAPI app entry point
│   ├── api/routes/
│   │   ├── scrape.py            # Scraping endpoints
│   │   ├── extract.py           # Extraction endpoints
│   │   ├── jobs.py              # Job management endpoints
│   │   └── health.py            # Health check
│   ├── core/
│   │   ├── config.py            # Settings (env vars)
│   │   ├── database.py          # Async SQLAlchemy setup
│   │   └── logging.py           # Structured logging
│   ├── models/
│   │   ├── db_models.py         # SQLAlchemy ORM models
│   │   └── schemas.py           # Pydantic request/response schemas
│   └── services/
│       ├── scraper.py           # httpx + Playwright scraping engine
│       ├── extractor.py         # LangChain AI extraction
│       ├── job_runner.py        # Async batch job runner
│       └── exporter.py          # JSON / CSV / Excel export
├── tests/
│   └── test_scraper.py          # Pytest test suite
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

---

## ⚙️ Configuration

All settings are managed via environment variables (`.env` file):

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | Required for AI extraction |
| `LLM_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `DATABASE_URL` | SQLite | Database connection string |
| `MAX_CONCURRENT_SCRAPES` | `10` | Global concurrency cap |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headlessly |
| `EXPORT_DIR` | `./exports` | Where to save export files |

See `.env.example` for the full list.

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add my feature'`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

[README.md](https://github.com/user-attachments/files/29403146/README.md)
