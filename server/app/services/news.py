from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from app.config import FIRECRAWL_API_KEY, FIRECRAWL_TIMEOUT, REQUEST_TIMEOUT, SESSION, TAVILY_API_KEY

logger = logging.getLogger(__name__)

NEWS_KEYWORDS = (
	"aftermarket",
	"spare parts",
	"parts",
	"service",
	"support",
	"digital",
	"digital transformation",
	"lifecycle service",
)
PRESS_KEYWORDS = ("press release", "press", "newsroom", "news", "media", "announcement")
LINKEDIN_KEYWORDS = ("linkedin", "post")
RECENT_SIGNAL_MAX_AGE_DAYS = 366
PRESS_PAGE_PATHS = (
	"/press",
	"/news",
	"/newsroom",
	"/media",
	"/press-releases",
	"/company/press",
	"/en/company/press",
	"/en/company/press/press-releases.php?page=1&filter%5B7%5D%5B%5D=all",
)


def _clean_text(value: Any) -> str:
	return re.sub(r"\s+", " ", str(value or "")).strip()


def _extract_domain(url: str | None) -> str:
	try:
		parsed = urlparse(url if str(url or "").startswith("http") else f"https://{url}")
		host = (parsed.netloc or parsed.path).split(":")[0].lower().strip()
		return re.sub(r"^www\.", "", host)
	except Exception:
		return ""


def _normalize_root_url(url: str | None) -> str:
	if not url:
		return ""
	raw = str(url).strip()
	if not raw:
		return ""
	if not raw.startswith("http"):
		raw = f"https://{raw}"
	parsed = urlparse(raw)
	host = parsed.netloc or parsed.path
	return f"https://{host}".rstrip("/") if host else ""


def _candidate_domains(*values: str | None) -> list[str]:
	seen: list[str] = []
	for value in values:
		root = _normalize_root_url(value)
		if root and root not in seen:
			seen.append(root)
	return seen


def _company_tokens(company_name: str) -> list[str]:
	raw = re.sub(r"[^A-Za-z0-9\s&-]", " ", company_name or "")
	parts = [p.lower() for p in raw.split() if len(p) >= 3]
	stop = {"the", "and", "inc", "ltd", "llc", "plc", "ag", "gmbh", "co", "corp", "corporation"}
	return [p for p in parts if p not in stop]


def _score_news_item(company_name: str, title: str, snippet: str) -> int:
	title_l = _clean_text(title).lower()
	snippet_l = _clean_text(snippet).lower()
	company_l = _clean_text(company_name).lower()
	score = 0

	if company_l and company_l in title_l:
		score += 6
	if company_l and company_l in snippet_l:
		score += 4

	for token in _company_tokens(company_name):
		if token in title_l:
			score += 2
		elif token in snippet_l:
			score += 1

	for keyword in NEWS_KEYWORDS:
		if keyword in title_l:
			score += 3
		elif keyword in snippet_l:
			score += 2

	for keyword in PRESS_KEYWORDS:
		if keyword in title_l:
			score += 2
		elif keyword in snippet_l:
			score += 1

	return score


def _has_signal_keyword(title: str, snippet: str) -> bool:
	combined = f"{_clean_text(title).lower()} {_clean_text(snippet).lower()}"
	return any(keyword in combined for keyword in NEWS_KEYWORDS)


def _parse_published_at(value: Any) -> datetime | None:
	text = _clean_text(value)
	if not text:
		return None

	candidates = [text]
	if text.endswith("Z"):
		candidates.append(text[:-1] + "+00:00")
	if re.fullmatch(r"\d{8}", text):
		candidates.append(f"{text[:4]}-{text[4:6]}-{text[6:8]}")

	for candidate in candidates:
		try:
			parsed = datetime.fromisoformat(candidate)
			return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
		except Exception:
			continue

	for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d.%m.%Y", "%d. %b %Y", "%d. %B %Y", "%b %d, %Y", "%B %d, %Y"):
		try:
			return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
		except Exception:
			continue
	return None


def _extract_date_from_text(value: str) -> str | None:
	text = _clean_text(value).replace("\\.", ".")
	if not text:
		return None

	matchers = (
		r"\b\d{4}-\d{2}-\d{2}\b",
		r"\b\d{4}/\d{2}/\d{2}\b",
		r"\b\d{8}\b",
		r"\b\d{1,2}\.\d{1,2}\.\d{4}\b",
		r"\b\d{1,2}\.\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{4}\b",
		r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}\b",
	)
	for pattern in matchers:
		match = re.search(pattern, text, flags=re.IGNORECASE)
		if match:
			return match.group(0)
	return None


def _is_recent_enough(published_at: Any) -> bool:
	parsed = _parse_published_at(published_at)
	if parsed is None:
		return True
	return parsed >= datetime.now(timezone.utc) - timedelta(days=RECENT_SIGNAL_MAX_AGE_DAYS)


def _is_company_match(company_name: str, title: str, snippet: str) -> bool:
	title_l = _clean_text(title).lower()
	snippet_l = _clean_text(snippet).lower()
	combined = f"{title_l} {snippet_l}"
	company_l = _clean_text(company_name).lower()
	tokens = _company_tokens(company_name)

	if company_l and company_l in combined:
		return True

	token_hits = 0
	for token in tokens:
		if token in combined:
			token_hits += 1

	if len(tokens) <= 1:
		return token_hits >= 1
	return token_hits >= 2


def _normalize_news_item(
	company_name: str,
	title: Any,
	url: Any,
	snippet: Any,
	published_at: Any,
	source_name: str,
) -> dict[str, Any] | None:
	clean_title = _clean_text(title)
	clean_url = _clean_text(url)
	clean_snippet = _clean_text(snippet)
	clean_published = _clean_text(published_at)
	if not clean_title or not clean_url:
		return None
	if not _is_company_match(company_name, clean_title, clean_snippet):
		return None
	if not _is_recent_enough(clean_published):
		return None

	score = _score_news_item(company_name, clean_title, clean_snippet)
	return {
		"title": clean_title,
		"url": clean_url,
		"snippet": clean_snippet,
		"published_at": clean_published or None,
		"source": source_name,
		"score": score,
	}


def _dedupe_news(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
	seen: dict[str, dict[str, Any]] = {}
	for item in items:
		key = _clean_text(item.get("url") or item.get("title")).lower()
		if not key:
			continue
		existing = seen.get(key)
		if existing is None or int(item.get("score", 0)) > int(existing.get("score", 0)):
			seen[key] = item
	return list(seen.values())


def _sort_and_trim_news(items: list[dict[str, Any]], max_items: int = 3) -> list[dict[str, Any]]:
	sorted_items = sorted(
		items,
		key=lambda item: (
			int(item.get("score", 0)),
			_clean_text(item.get("published_at")).lower(),
			_clean_text(item.get("title")).lower(),
		),
		reverse=True,
	)
	result: list[dict[str, Any]] = []
	for item in sorted_items[:max_items]:
		result.append({k: v for k, v in item.items() if k != "score"})
	return result


def fetch_tavily_news(company_name: str) -> list[dict[str, Any]]:
	if not TAVILY_API_KEY:
		return []

	query = f'"{company_name}" aftermarket OR "spare parts" OR "service" OR "digital transformation"'
	payload = {
		"api_key": TAVILY_API_KEY,
		"query": query,
		"max_results": 5,
		"search_depth": "basic",
		"topic": "news",
		"include_answer": False,
	}
	try:
		response = SESSION.post("https://api.tavily.com/search", json=payload, timeout=REQUEST_TIMEOUT)
		response.raise_for_status()
		body = response.json()
		results: list[dict[str, Any]] = []
		for item in body.get("results", []) if isinstance(body, dict) else []:
			if not isinstance(item, dict):
				continue
			news_item = _normalize_news_item(
				company_name=company_name,
				title=item.get("title"),
				url=item.get("url"),
				snippet=item.get("content"),
				published_at=item.get("published_date"),
				source_name="tavily",
			)
			if news_item is not None:
				results.append(news_item)
		return results
	except Exception as exc:
		logger.warning("Tavily news lookup failed for %s: %s", company_name, exc)
		return []


def fetch_tavily_company_press(company_name: str, resolved_domain: str | None, website_url: str | None = None) -> list[dict[str, Any]]:
	if not TAVILY_API_KEY:
		return []

	results: list[dict[str, Any]] = []
	for domain_root in _candidate_domains(resolved_domain, website_url):
		clean_domain = _extract_domain(domain_root)
		if not clean_domain:
			continue

		query = (
			f'"{company_name}" ("press release" OR newsroom OR announcement) '
			'("aftermarket" OR "spare parts" OR "service" OR "digital transformation")'
		)
		payload = {
			"api_key": TAVILY_API_KEY,
			"query": query,
			"max_results": 8,
			"search_depth": "advanced",
			"include_answer": False,
			"include_domains": [clean_domain],
		}
		try:
			response = SESSION.post("https://api.tavily.com/search", json=payload, timeout=REQUEST_TIMEOUT)
			response.raise_for_status()
			body = response.json()
			for item in body.get("results", []) if isinstance(body, dict) else []:
				if not isinstance(item, dict):
					continue
				news_item = _normalize_news_item(
					company_name=company_name,
					title=item.get("title"),
					url=item.get("url"),
					snippet=item.get("content"),
					published_at=item.get("published_date"),
					source_name="company_press_search",
				)
				if news_item is None:
					continue
				if not news_item.get("published_at"):
					continue
				url_l = _clean_text(news_item.get("url")).lower()
				if clean_domain and clean_domain not in _extract_domain(url_l):
					continue
				if not _has_signal_keyword(str(news_item.get("title")), str(news_item.get("snippet"))):
					continue
				title_l = _clean_text(news_item.get("title")).lower()
				press_like = (
					any(keyword in title_l for keyword in PRESS_KEYWORDS)
					or any(token in url_l for token in ("/press", "/news", "/newsroom", "/media", "press-release", "announcement"))
				)
				if not press_like:
					continue
				if any(keyword in url_l for keyword in ("press", "news", "media", "announcement")):
					news_item["score"] = int(news_item.get("score", 0)) + 3
				results.append(news_item)
		except Exception as exc:
			logger.warning("Company press lookup failed for %s (%s): %s", company_name, clean_domain, exc)
	return results


def _build_press_page_urls(*domains: str | None) -> list[str]:
	urls: list[str] = []
	for root in _candidate_domains(*domains):
		for path in PRESS_PAGE_PATHS:
			candidate = f"{root}{path}"
			if candidate not in urls:
				urls.append(candidate)
	return urls


def _fetch_firecrawl_markdown(url: str) -> str:
	if not FIRECRAWL_API_KEY:
		return ""
	try:
		response = requests.post(
			"https://api.firecrawl.dev/v1/scrape",
			headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}", "Content-Type": "application/json"},
			json={"url": url, "formats": ["markdown"], "onlyMainContent": True},
			timeout=FIRECRAWL_TIMEOUT,
		)
		response.raise_for_status()
		body = response.json() if isinstance(response.json(), dict) else {}
		data = body.get("data", {}) if isinstance(body, dict) else {}
		text = str(data.get("markdown") or data.get("content") or "")
		text = text.replace("\r\n", "\n").replace("\r", "\n")
		return re.sub(r"[ \t]+", " ", text).strip()
	except Exception as exc:
		logger.warning("Firecrawl press scrape failed for %s: %s", url, exc)
		return ""


def _extract_markdown_press_items(company_name: str, base_url: str, markdown: str) -> list[dict[str, Any]]:
	results: list[dict[str, Any]] = []
	if not markdown:
		return results

	junk_titles = {"back", "page up", "share this page"}

	for raw_line in markdown.splitlines():
		line = _clean_text(raw_line)
		if not line:
			continue
		for title, href in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", line):
			if title.strip().lower() in junk_titles or title.strip().startswith("!"):
				continue
			absolute_url = urljoin(base_url, href)
			if absolute_url.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg")):
				continue
			published_at = _extract_date_from_text(line)
			item = _normalize_news_item(
				company_name=company_name,
				title=title,
				url=absolute_url,
				snippet=line,
				published_at=published_at,
				source_name="company_press_firecrawl",
			)
			if item is None:
				continue
			if not _has_signal_keyword(title, line):
				continue
			item["score"] = int(item.get("score", 0)) + 4
			results.append(item)

	rich_link_pattern = re.compile(
		r"\[(?P<date>[^\]]{4,40}?)\\*\s*\n?\*\*(?P<title>[^*]+)\*\*\]\((?P<url>https?://[^)\s\"]+)",
		flags=re.IGNORECASE,
	)
	for match in rich_link_pattern.finditer(markdown):
		title = _clean_text(match.group("title"))
		absolute_url = urljoin(base_url, match.group("url"))
		published_at = _extract_date_from_text(match.group("date"))
		item = _normalize_news_item(
			company_name=company_name,
			title=title,
			url=absolute_url,
			snippet=f"{match.group('date')} {title}",
			published_at=published_at,
			source_name="company_press_firecrawl",
		)
		if item is None:
			continue
		if not _has_signal_keyword(title, f"{match.group('date')} {title}"):
			continue
		item["score"] = int(item.get("score", 0)) + 5
		results.append(item)
	return results


def fetch_company_press_from_firecrawl(company_name: str, resolved_domain: str | None, website_url: str | None = None) -> list[dict[str, Any]]:
	for press_url in _build_press_page_urls(resolved_domain, website_url):
		markdown = _fetch_firecrawl_markdown(press_url)
		if not markdown or len(markdown) < 120:
			continue
		items = _extract_markdown_press_items(company_name, press_url, markdown)
		if items:
			return items
	return []


def find_recent_news(company_name: str, resolved_domain: str | None = None, website_url: str | None = None) -> list[dict[str, Any]]:
	tavily_items = [item for item in fetch_tavily_news(company_name) if int(item.get("score", 0)) >= 5]
	items = _dedupe_news(tavily_items)
	# Press-release fallbacks are intentionally disabled for now.
	# if len(items) < 3:
	# 	press_items = [item for item in fetch_tavily_company_press(company_name, resolved_domain, website_url) if int(item.get("score", 0)) >= 5]
	# 	items = _dedupe_news(items + press_items)
	# if len(items) < 3:
	# 	firecrawl_press_items = [item for item in fetch_company_press_from_firecrawl(company_name, resolved_domain, website_url) if int(item.get("score", 0)) >= 5]
	# 	items = _dedupe_news(items + firecrawl_press_items)
	return _sort_and_trim_news(items, max_items=3)
