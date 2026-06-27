# AI Web Scraper + Data Extractor
# Python 3.11+

# ── Web Framework ──────────────────────────────────────────────────────────────
fastapi==0.115.5
uvicorn[standard]==0.32.1
python-multipart==0.0.12

# ── Database ───────────────────────────────────────────────────────────────────
sqlalchemy[asyncio]==2.0.36
aiosqlite==0.20.0               # SQLite async driver (dev)
asyncpg==0.30.0                 # PostgreSQL async driver (prod)

# ── Config ─────────────────────────────────────────────────────────────────────
pydantic==2.10.2
pydantic-settings==2.6.1

# ── HTTP Scraping ──────────────────────────────────────────────────────────────
httpx==0.28.0
beautifulsoup4==4.12.3
lxml==5.3.0

# ── Browser Scraping ───────────────────────────────────────────────────────────
playwright==1.49.0

# ── AI / LangChain ────────────────────────────────────────────────────────────
langchain==0.3.9
langchain-openai==0.2.10
langchain-core==0.3.21
openai==1.57.0

# ── Export ─────────────────────────────────────────────────────────────────────
openpyxl==3.1.5

# ── Testing ────────────────────────────────────────────────────────────────────
pytest==8.3.4
pytest-asyncio==0.24.0
httpx==0.28.0                   # for TestClient
