import os
from pathlib import Path

import requests
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
SERVER_DIR = APP_DIR.parent
ROOT_DIR = SERVER_DIR.parent

load_dotenv(ROOT_DIR / ".env")
load_dotenv(SERVER_DIR / ".env")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip() or "llama-3.3-70b-versatile"
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "").strip()
CUFINDER_API_KEY = os.getenv("CUFINDER_API_KEY", "").strip()
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "").strip()
TECHNOLOGY_CHECKER_API_KEY = os.getenv("TECHNOLOGY_CHECKER_API_KEY", "").strip()

if not GEMINI_API_KEY and GOOGLE_API_KEY:
	GEMINI_API_KEY = GOOGLE_API_KEY
if GEMINI_API_KEY:
	os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
	os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

REQUEST_TIMEOUT = 5
FIRECRAWL_TIMEOUT = 8
MAX_CONTENT_CHARS = 5000
CACHE_DB_PATH = os.getenv("CACHE_DB_PATH", str(SERVER_DIR / "research_cache.sqlite3")).strip() or str(SERVER_DIR / "research_cache.sqlite3")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "86400").strip() or "86400")
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
LEGACY_BOT_USER_AGENT = "sales-agent/1.0 (+https://local.enrichsalesagent)"
USER_AGENT = os.getenv("USER_AGENT", DEFAULT_USER_AGENT).strip() or DEFAULT_USER_AGENT
if USER_AGENT == LEGACY_BOT_USER_AGENT:
	USER_AGENT = DEFAULT_USER_AGENT
os.environ["USER_AGENT"] = USER_AGENT

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})

# Backward-compatible alias.
session = SESSION
