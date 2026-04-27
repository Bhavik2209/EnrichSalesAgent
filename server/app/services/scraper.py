from __future__ import annotations

import json
import logging
import os
import re
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from app.config import FIRECRAWL_API_KEY, FIRECRAWL_TIMEOUT, GEMINI_API_KEY, GROQ_API_KEY, MAX_CONTENT_CHARS, REQUEST_TIMEOUT, SESSION
from app.prompts import SCRAPER_PROFILE_PROMPT_TEMPLATE, SCRAPER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

MIN_DIRECT_PROFILE_TEXT_CHARS = 200
MIN_FIRECRAWL_PROFILE_TEXT_CHARS = 120
MAX_PROFILE_URLS_TO_TRY = 4
MAX_FIRECRAWL_FALLBACKS = 1


def _debug_what_they_make(message: str, *args: Any) -> None:
    formatted = message % args if args else message
    print(formatted)
    logger.info(formatted)

try:
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
    from langchain_core.tools import tool
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_groq import ChatGroq  # type: ignore[import-not-found]

    HAS_LANGCHAIN = True
except Exception:
    HAS_LANGCHAIN = False

    def tool(*_args: Any, **_kwargs: Any):
        def _decorator(func: Any) -> Any:
            return func

        return _decorator


GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash"); GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


@tool
def fetch_page_direct(url: str) -> str:
    """Fetches and cleans HTML page text directly. Use this first - it's fast and free. If it returns less than 200 characters, the page may be JS-rendered, try Firecrawl instead."""
    try:
        r = SESSION.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        if "text/html" not in r.headers.get("content-type", ""):
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "button"]):
            tag.decompose()
        m1 = soup.find("meta", attrs={"name": "description"})
        m2 = soup.find("meta", attrs={"property": "og:description"})
        text = f"{(m1.get('content', '') if m1 else '')} {(m2.get('content', '') if m2 else '')} {soup.get_text(' ', strip=True)}"
        return re.sub(r"\s+", " ", text).strip()[:MAX_CONTENT_CHARS]
    except Exception:
        return ""


@tool
def fetch_page_firecrawl(url: str) -> str:
    """Fetches page content via Firecrawl markdown scrape. Use this only if fetch_page_direct returned less than 200 characters. Costs a Firecrawl credit - avoid calling unnecessarily."""
    if not FIRECRAWL_API_KEY:
        return ""
    try:
        r = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}", "Content-Type": "application/json"},
            json={"url": url, "formats": ["markdown"], "onlyMainContent": True},
            timeout=FIRECRAWL_TIMEOUT,
        )
        r.raise_for_status()
        body = r.json() if isinstance(r.json(), dict) else {}
        data = body.get("data", {}) if isinstance(body, dict) else {}
        text = str(data.get("markdown") or data.get("content") or "")
        return re.sub(r"\s+", " ", text).strip()[:MAX_CONTENT_CHARS]
    except Exception as exc:
        print(f"[firecrawl] failed for {url}: {exc}")
        return ""


@tool
def extract_what_they_make_from_text(text: str) -> str | None:
    """Extracts what the company manufactures or provides from page text using regex. Call this after you have fetched sufficient page content (>200 chars)."""
    if not text:
        return None
    patterns = [
        r"manufactures? (?:and sells? )?([A-Za-z0-9,\-&/()\s]{12,180})",
        r"leading provider of ([A-Za-z0-9,\-&/()\s]{12,180})",
        r"supplier of ([A-Za-z0-9,\-&/()\s]{12,180})",
        r"developer of ([A-Za-z0-9,\-&/()\s]{12,180})",
        r"our products include ([A-Za-z0-9,\-&/()\s]{12,180})",
    ]
    stops, bad = (" for ", " with ", " that ", " which ", " across ", "."), {"solutions", "services", "customers", "operations", "communities", "careers", "sustainability"}
    for p in patterns:
        for m in re.finditer(p, text, flags=re.IGNORECASE):
            c = re.sub(r"\s+", " ", m.group(1)).strip(" ,.-")
            lc = c.lower()
            for s in stops:
                i = lc.find(s)
                if i > 0:
                    c = c[:i].strip(" ,.-")
                    lc = c.lower()
            if len(c) >= 10 and len(c.split()) <= 18 and lc not in bad and not any(lc.startswith(f"{w} ") for w in bad):
                return c
    return None


def _normalize_root_url(raw_url: str) -> str:
    raw = (raw_url or "").strip().rstrip("/")
    if not raw:
        return ""
    if not raw.startswith("http"):
        raw = f"https://{raw}"
    p = urlparse(raw)
    return f"https://{p.netloc or p.path}".rstrip("/")


def _build_profile_urls(*candidate_domains: str) -> list[str]:
    roots: list[str] = []
    for candidate in candidate_domains:
        root = _normalize_root_url(candidate)
        if root and root not in roots:
            roots.append(root)

    urls: list[str] = []
    suffixes = ["", "/about", "/about-us"]
    for root in roots:
        for suffix in suffixes:
            url = f"{root}{suffix}"
            if url not in urls:
                urls.append(url)
    return urls


def _parse_json(text: Any) -> dict[str, Any]:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        out = json.loads(raw)
        return out if isinstance(out, dict) else {}
    except Exception:
        s, e = raw.find("{"), raw.rfind("}")
        if s >= 0 and e > s:
            try:
                out = json.loads(raw[s : e + 1])
                return out if isinstance(out, dict) else {}
            except Exception:
                return {}
    return {}


def _clean_markdown_profile_text(text: str) -> str:
    cleaned = str(text or "")
    if not cleaned:
        return ""

    if "# " in cleaned:
        cleaned = cleaned[cleaned.find("# ") :]

    cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", cleaned)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"\b\d{1,2}/\d{1,2}/\d{4},\s+\d{1,2}:\d{2}:\d{2}\s+[AP]M\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b\d+\.\s+\d+\b", " ", cleaned)
    cleaned = re.sub(r"\s+#\s+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:MAX_CONTENT_CHARS]


def _looks_like_noisy_description(text: str | None) -> bool:
    value = str(text or "").strip()
    if not value:
        return True
    noisy_patterns = (
        r"https?://",
        r"\[[^\]]+\]\([^)]+\)",
        r"\b\d{1,2}/\d{1,2}/\d{4},\s+\d{1,2}:\d{2}:\d{2}\s+[AP]M\b",
    )
    if any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in noisy_patterns):
        return True
    if value.count(" - ") >= 3:
        return True
    return False


def _shorten_description(text: str | None, max_sentences: int = 3, max_chars: int = 320) -> str | None:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if not value:
        return None

    sentences = re.split(r"(?<=[.!?])\s+", value)
    kept: list[str] = []
    for sentence in sentences:
        clean = sentence.strip()
        if not clean:
            continue
        kept.append(clean)
        if len(kept) >= max_sentences:
            break

    shortened = " ".join(kept).strip() if kept else value
    if len(shortened) > max_chars:
        shortened = shortened[:max_chars].rstrip(" ,;:-")
        if shortened and shortened[-1] not in ".!?":
            shortened += "."
    return shortened or None


def _shorten_llm_description(text: str | None) -> str | None:
    return _shorten_description(text, max_sentences=2, max_chars=220)


def _shorten_website_description(text: str | None) -> str | None:
    return _shorten_description(text, max_sentences=4, max_chars=420)


def _fallback_description_from_text(text: str) -> str | None:
    cleaned = _clean_markdown_profile_text(text)
    if not cleaned:
        return None

    sentence_matches = re.findall(r"[A-Z][^.?!]{25,220}[.?!]", cleaned)
    if sentence_matches:
        return _shorten_website_description(" ".join(sentence_matches[:4]))

    return _shorten_website_description(cleaned[:420].strip() or None)


def _invoke_profile_llm(text: str) -> dict[str, Any]:
    if not text:
        return {}

    prompt = SCRAPER_PROFILE_PROMPT_TEMPLATE.format(input_text=_clean_markdown_profile_text(text)[:2500])
    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, google_api_key=GEMINI_API_KEY, temperature=0) if GEMINI_API_KEY else None
    if llm is None and GROQ_API_KEY:
        llm = ChatGroq(model=GROQ_MODEL, groq_api_key=GROQ_API_KEY, temperature=0)
    if llm is None:
        return {}

    try:
        response = llm.invoke(prompt)
        parsed = _parse_json(getattr(response, "content", ""))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def build_scraper_agent() -> dict[str, Any] | None:
    if not HAS_LANGCHAIN:
        return None
    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, google_api_key=GEMINI_API_KEY, temperature=0) if GEMINI_API_KEY else None
    if llm is None and GROQ_API_KEY:
        llm = ChatGroq(model=GROQ_MODEL, groq_api_key=GROQ_API_KEY, temperature=0)
    if llm is None:
        return None
    tools = [fetch_page_direct, fetch_page_firecrawl, extract_what_they_make_from_text]
    return {"llm": llm.bind_tools(tools), "tools": {t.name: t for t in tools}}


def _run_agent(agent: dict[str, Any], urls: list[str]) -> tuple[dict, str]:
    msgs = [SystemMessage(content=SCRAPER_SYSTEM_PROMPT), HumanMessage(content=json.dumps({"candidate_urls": urls}, ensure_ascii=True))]
    for _ in range(10):
        ai = agent["llm"].invoke(msgs)
        calls = getattr(ai, "tool_calls", None) or []
        if not calls:
            out = _parse_json(getattr(ai, "content", ""))
            method = out.get("fetch_method") if out.get("fetch_method") in {"direct", "firecrawl"} else "failed"
            data = {k: out.get(k) for k in ["what_they_make", "description", "source_url", "fetch_method"] if out.get(k) is not None}
            return (data, method)
        msgs.append(ai)
        for c in calls:
            t = agent["tools"].get(c.get("name", ""))
            try:
                result = t.invoke(c.get("args", {})) if t is not None else ""
            except Exception:
                result = ""
            msgs.append(ToolMessage(content=json.dumps(result, ensure_ascii=True, default=str), tool_call_id=c.get("id", "")))
    return ({}, "failed")


def get_about_page_text(resolved_domain: str, website_url: str = "") -> tuple[dict, str]:
    urls = _build_profile_urls(website_url, resolved_domain)
    if not urls:
        _debug_what_they_make(
            "[what_they_make] no candidate urls resolved from domain=%s website=%s",
            resolved_domain,
            website_url,
        )
        return ({}, "failed")

    firecrawl_attempts = 0
    _debug_what_they_make("[what_they_make] trying candidate urls: %s", urls[:MAX_PROFILE_URLS_TO_TRY])
    for url in urls[:MAX_PROFILE_URLS_TO_TRY]:
        text = fetch_page_direct.invoke({"url": url})
        used_firecrawl_for_url = False
        if not isinstance(text, str):
            text = ""
        _debug_what_they_make("[what_they_make] url=%s text_len=%s", url, len(text))
        if len(text) == 0:
            if firecrawl_attempts < MAX_FIRECRAWL_FALLBACKS:
                firecrawl_attempts += 1
                used_firecrawl_for_url = True
                firecrawl_text = fetch_page_firecrawl.invoke({"url": url})
                if not isinstance(firecrawl_text, str):
                    firecrawl_text = ""
                _debug_what_they_make("[what_they_make] firecrawl url=%s text_len=%s", url, len(firecrawl_text))
                text = firecrawl_text
            else:
                _debug_what_they_make("[what_they_make] skipping firecrawl for url=%s because fallback budget is exhausted", url)
        min_len = MIN_FIRECRAWL_PROFILE_TEXT_CHARS if used_firecrawl_for_url and len(text) > 0 else MIN_DIRECT_PROFILE_TEXT_CHARS
        if len(text) < min_len:
            _debug_what_they_make("[what_they_make] skipping url=%s because text_len < %s", url, min_len)
            continue

        what_they_make = extract_what_they_make_from_text.invoke({"text": text})
        fallback_description = _fallback_description_from_text(text)
        llm_profile: dict[str, Any] = {}
        llm_what_they_make = None
        llm_description = None

        # Avoid an extra LLM round-trip when we already have a usable factual sentence.
        if not what_they_make and not fallback_description:
            llm_profile = _invoke_profile_llm(text)
            llm_what_they_make = llm_profile.get("what_they_make") if isinstance(llm_profile.get("what_they_make"), str) else None
            llm_description = llm_profile.get("description") if isinstance(llm_profile.get("description"), str) else None

        _debug_what_they_make(
            "[what_they_make] url=%s regex_result=%s llm_result=%s",
            url,
            what_they_make,
            llm_what_they_make,
        )
        description = None
        if not _looks_like_noisy_description(llm_description):
            description = _shorten_llm_description(llm_description)
        if not description:
            description = _shorten_website_description(fallback_description)
        data = {
            "description": (description or "").strip(),
            "source_url": url,
            "fetch_method": "firecrawl" if used_firecrawl_for_url else "direct",
        }
        final_what_they_make = what_they_make if isinstance(what_they_make, str) and what_they_make else llm_what_they_make
        if isinstance(final_what_they_make, str) and final_what_they_make:
            data["what_they_make"] = final_what_they_make.strip()
            _debug_what_they_make("[what_they_make] selected url=%s final_result=%s", url, final_what_they_make.strip())
        else:
            _debug_what_they_make("[what_they_make] selected url=%s but no what_they_make extracted", url)
        return (data, "direct")

    _debug_what_they_make("[what_they_make] no usable profile page found from candidate urls")
    return ({}, "failed")
