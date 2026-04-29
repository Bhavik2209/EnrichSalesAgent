import os
from pathlib import Path

import requests
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
SERVER_DIR = APP_DIR.parent
ROOT_DIR = SERVER_DIR.parent

load_dotenv(ROOT_DIR / ".env")
load_dotenv(SERVER_DIR / ".env")


def _parse_key_list(value: str) -> list[str]:
	keys: list[str] = []
	for item in str(value or "").split(","):
		key = item.strip()
		if key and key not in keys:
			keys.append(key)
	return keys


def _parse_numbered_key_env(prefix: str) -> list[str]:
	keyed_items: list[tuple[int, str]] = []
	for env_name, env_value in os.environ.items():
		if not env_name.startswith(prefix):
			continue
		suffix = env_name[len(prefix) :]
		if not suffix.isdigit():
			continue
		key = str(env_value or "").strip()
		if not key:
			continue
		keyed_items.append((int(suffix), key))
	keyed_items.sort(key=lambda item: item[0])
	keys: list[str] = []
	for _, key in keyed_items:
		if key not in keys:
			keys.append(key)
	return keys

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

GEMINI_API_KEYS = _parse_key_list(os.getenv("GEMINI_API_KEYS", ""))
primary_gemini_keys = _parse_key_list(GEMINI_API_KEY)
if primary_gemini_keys:
	GEMINI_API_KEYS = primary_gemini_keys + [key for key in GEMINI_API_KEYS if key not in primary_gemini_keys]
google_gemini_keys = _parse_key_list(GOOGLE_API_KEY)
if google_gemini_keys:
	if not primary_gemini_keys:
		GEMINI_API_KEYS = google_gemini_keys + [key for key in GEMINI_API_KEYS if key not in google_gemini_keys]
	else:
		GEMINI_API_KEYS = GEMINI_API_KEYS + [key for key in google_gemini_keys if key not in GEMINI_API_KEYS]

CUFINDER_API_KEYS = _parse_key_list(os.getenv("CUFINDER_API_KEYS", ""))
primary_cufinder_keys = _parse_key_list(CUFINDER_API_KEY)
if primary_cufinder_keys:
	CUFINDER_API_KEYS = primary_cufinder_keys + [key for key in CUFINDER_API_KEYS if key not in primary_cufinder_keys]
legacy_cufinder_keys = _parse_numbered_key_env("CUFINDER_API_KEY")
if legacy_cufinder_keys:
	CUFINDER_API_KEYS = CUFINDER_API_KEYS + [key for key in legacy_cufinder_keys if key not in CUFINDER_API_KEYS]

HUNTER_API_KEYS = _parse_key_list(os.getenv("HUNTER_API_KEYS", ""))
if HUNTER_API_KEY:
	HUNTER_API_KEYS = [HUNTER_API_KEY] + [key for key in HUNTER_API_KEYS if key != HUNTER_API_KEY]

GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else ""
CUFINDER_API_KEY = CUFINDER_API_KEYS[0] if CUFINDER_API_KEYS else ""
HUNTER_API_KEY = HUNTER_API_KEYS[0] if HUNTER_API_KEYS else ""

if GEMINI_API_KEY:
	os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
	os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

REQUEST_TIMEOUT = 5
FIRECRAWL_TIMEOUT = 8
MAX_CONTENT_CHARS = 5000
CACHE_DB_PATH = os.getenv("CACHE_DB_PATH", str(SERVER_DIR / "research_cache.sqlite3")).strip() or str(SERVER_DIR / "research_cache.sqlite3")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "86400").strip() or "86400")
CORS_ALLOWED_ORIGINS = [
	origin.strip()
	for origin in os.getenv(
		"CORS_ALLOWED_ORIGINS",
		"http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173,http://127.0.0.1:5173,https://enrichsalesagent.vercel.app,https://enrichsalesagent-project.vercel.app",
	).split(",")
	if origin.strip()
]
CORS_ALLOWED_ORIGIN_REGEX = (
	os.getenv(
		"CORS_ALLOWED_ORIGIN_REGEX",
		r"https://([a-z0-9-]+\.)?vercel\.app",
	).strip()
	or None
)
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
