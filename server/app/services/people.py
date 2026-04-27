from __future__ import annotations

import json
import logging
import os
import re
from typing import Any
from urllib.parse import quote, urljoin, urlparse

from bs4 import BeautifulSoup

from app.config import GEMINI_API_KEY, GROQ_API_KEY, REQUEST_TIMEOUT, SESSION, TAVILY_API_KEY

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

TITLE_FILTER_KEYWORDS = (
	"aftermarket",
	"service",
	"sales",
	"commercial",
	"director",
	"vp",
	"vice president",
	"head of",
	"manager",
	"general manager",
	"ceo",
	"cto",
	"coo",
)

LEADERSHIP_PATHS = [
	"/about",
	"/team",
	"/leadership",
	"/management",
	"/about-us/team",
	"/company/team",
	"/our-team",
	"/about/leadership",
]

DEFAULT_TITLE_KEYWORDS = "aftermarket service sales commercial director vp"


def extract_domain(url: str) -> str:
	try:
		parsed = urlparse(url if "://" in url else f"https://{url}")
		host = (parsed.netloc or parsed.path).split(":")[0].lower().strip()
		return re.sub(r"^www\.", "", host)
	except Exception:
		return str(url).lower().strip()


def _is_likely_person_name(text: str) -> bool:
	clean = re.sub(r"\s+", " ", str(text or "")).strip()
	if not clean or len(clean.split()) < 2:
		return False
	if any(tok in clean.lower() for tok in ("team", "leadership", "management", "company", "about")):
		return False
	return bool(re.match(r"^[A-Z][A-Za-z\-\.'`]+(?:\s+[A-Z][A-Za-z\-\.'`]+){1,4}$", clean))


def _title_relevant(title: str) -> bool:
	t = str(title or "").lower()
	return any(k in t for k in TITLE_FILTER_KEYWORDS)


def _normalize_person(name: str, title: str, linkedin_url: str | None = None) -> dict[str, str] | None:
	n = re.sub(r"\s+", " ", str(name or "")).strip()
	t = re.sub(r"\s+", " ", str(title or "")).strip()
	l = str(linkedin_url or "").strip()
	if not (_is_likely_person_name(n) and _title_relevant(t)):
		return None
	return {"name": n, "title": t, "linkedin_url": l}


def _extract_persons_from_container(container: Any) -> list[dict[str, str]]:
	results: list[dict[str, str]] = []
	for heading in container.find_all(["h2", "h3", "h4", "strong"]):
		name = re.sub(r"\s+", " ", heading.get_text(" ", strip=True)).strip()
		if not _is_likely_person_name(name):
			continue
		title_el = heading.find_next(["p", "span", "div"])
		title = title_el.get_text(" ", strip=True) if title_el else ""
		linkedin = ""
		link_el = container.find("a", href=re.compile(r"linkedin\.com/in/", re.IGNORECASE))
		if link_el:
			href = str(link_el.get("href", "")).strip()
			linkedin = href if href.startswith("http") else f"https://{href.lstrip('/')}"
		person = _normalize_person(name, title, linkedin)
		if person is not None:
			results.append(person)
	return results


def _extract_people_from_heading_scan(soup: Any) -> list[dict[str, str]]:
	people: list[dict[str, str]] = []
	for heading in soup.find_all(["h2", "h3", "h4"]):
		name = re.sub(r"\s+", " ", heading.get_text(" ", strip=True)).strip()
		if not _is_likely_person_name(name):
			continue
		near = heading.find_next(["p", "span", "div"])
		title = near.get_text(" ", strip=True) if near else ""
		link = heading.find_next("a", href=re.compile(r"linkedin\.com/in/", re.IGNORECASE))
		linkedin = str(link.get("href", "")).strip() if link else ""
		if linkedin and not linkedin.startswith("http"):
			linkedin = f"https://{linkedin.lstrip('/')}"
		person = _normalize_person(name, title, linkedin)
		if person is not None:
			people.append(person)
	return people


def _scrape_people_from_url(url: str, class_pattern: Any) -> list[dict[str, str]]:
	try:
		response = SESSION.get(url, timeout=REQUEST_TIMEOUT)
		response.raise_for_status()
	except Exception:
		return []

	soup = BeautifulSoup(response.text, "html.parser")
	people: list[dict[str, str]] = []
	for container in soup.find_all(attrs={"class": class_pattern}):
		people.extend(_extract_persons_from_container(container))
	people.extend(_extract_people_from_heading_scan(soup))
	return list({(p["name"].lower(), p["title"].lower()): p for p in people}.values())


try:
	from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
	from langchain_core.tools import tool
	from langchain_google_genai import ChatGoogleGenerativeAI
	from langchain_groq import ChatGroq  # type: ignore[import-not-found]

	HAS_LANGCHAIN = True
except Exception:
	HAS_LANGCHAIN = False
	HumanMessage = SystemMessage = ToolMessage = None  # type: ignore[assignment]

	def tool(*_args: Any, **_kwargs: Any):
		def _decorator(func: Any) -> Any:
			return func

		return _decorator


@tool
def scrape_leadership_page(resolved_domain: str) -> list[dict[str, str]]:
	"""Scrapes the company website for leadership/team pages to find real named executives with titles. Try this first - it is free and often lists service/sales/aftermarket leads directly."""
	try:
		domain = extract_domain(resolved_domain)
		if not domain:
			return []
		base = f"https://{domain}"
		class_pattern = re.compile(r"team|leadership|people|member|person|executive|management", re.IGNORECASE)

		for path in LEADERSHIP_PATHS:
			url = urljoin(base, path)
			people = _scrape_people_from_url(url, class_pattern)
			if people:
				return people

		return []
	except Exception as exc:
		logger.warning("scrape_leadership_page failed for %s: %s", resolved_domain, exc)
		return []


def _name_looks_like_company(name: str) -> bool:
	clean = re.sub(r"\s+", " ", str(name or "")).strip()
	if not clean:
		return True
	if any(tok in clean.upper() for tok in (" LLC", " INC", " LTD", " GMBH", " PLC", " CORP")):
		return True
	letters = re.sub(r"[^A-Za-z]", "", clean)
	return bool(letters and letters.isupper() and len(letters) > 4)


def _parse_linkedin_result(title_text: str, url: str) -> dict[str, str] | None:
	title_text = re.sub(r"\s+", " ", str(title_text or "")).strip()
	if " - " not in title_text:
		return None
	name, rem = title_text.split(" - ", 1)
	role = rem.split(" at ", 1)[0].strip()
	name = name.strip()
	if _name_looks_like_company(name) or not _is_likely_person_name(name):
		return None
	if not role:
		return None
	return {"name": name, "title": role, "linkedin_url": url}


def _collect_linkedin_from_tavily(query: str) -> list[dict[str, str]]:
	payload = {
		"api_key": TAVILY_API_KEY,
		"query": query,
		"max_results": 5,
		"search_depth": "basic",
		"include_answer": False,
		"include_domains": ["linkedin.com"],
		"exclude_domains": [],
	}
	response = SESSION.post("https://api.tavily.com/search", json=payload, timeout=REQUEST_TIMEOUT)
	response.raise_for_status()
	data = response.json()
	parsed: list[dict[str, str]] = []
	for item in data.get("results", []):
		url = str(item.get("url", "")).strip()
		title_text = str(item.get("title", "")).strip()
		if "linkedin.com/in/" not in url.lower():
			continue
		person = _parse_linkedin_result(title_text, url)
		if person is not None:
			parsed.append(person)
	return parsed


def _collect_linkedin_from_ddg(query: str) -> list[dict[str, str]]:
	ddg_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
	response = SESSION.get(ddg_url, timeout=REQUEST_TIMEOUT)
	response.raise_for_status()
	soup = BeautifulSoup(response.text, "html.parser")
	parsed: list[dict[str, str]] = []
	for item in soup.select(".result__body")[:5]:
		title_el = item.select_one(".result__title")
		link_el = item.select_one("a.result__a")
		url = str(link_el.get("href", "")).strip() if link_el else ""
		title_text = title_el.get_text(" ", strip=True) if title_el else ""
		if "linkedin.com/in/" not in url.lower():
			continue
		person = _parse_linkedin_result(title_text, url)
		if person is not None:
			parsed.append(person)
	return parsed


@tool
def search_person_linkedin(company_name: str, title_keywords: str) -> list[dict[str, str]]:
	"""Searches LinkedIn via web search for real people at the company matching the given title keywords. Use this if website scraping found nothing. Pass title_keywords like 'aftermarket service director' or 'VP sales'."""
	try:
		query = f'site:linkedin.com/in "{company_name}" "{title_keywords}"'
		results = _collect_linkedin_from_tavily(query) if TAVILY_API_KEY else _collect_linkedin_from_ddg(query)

		deduped = list({r["linkedin_url"]: r for r in results if r.get("linkedin_url")}.values())
		return deduped[:3]
	except Exception as exc:
		logger.warning("search_person_linkedin failed for %s: %s", company_name, exc)
		return []


def suggest_title_from_context(aftermarket_data: dict, enrichment_data: dict) -> dict[str, str]:
	emp = 0
	try:
		emp = int(str(enrichment_data.get("employee_count") or "0").replace(",", "").strip() or 0)
	except Exception:
		emp = 0

	if aftermarket_data.get("aftermarket_footprint"):
		if aftermarket_data.get("service_page") and emp > 500:
			return {
				"suggested_title": "VP of Aftermarket Services",
				"reasoning": "Company has dedicated service infrastructure and significant headcount",
			}
		if aftermarket_data.get("parts_page"):
			return {
				"suggested_title": "Director of Parts & Service",
				"reasoning": "Company has dedicated parts pages indicating aftermarket focus",
			}
		return {
			"suggested_title": "Director of After-Sales Services",
			"reasoning": "Company shows aftermarket presence on website",
		}

	if emp > 5000:
		return {
			"suggested_title": "VP of Sales & Commercial Operations",
			"reasoning": "Large enterprise - decision maker likely at VP level",
		}
	if emp > 500:
		return {
			"suggested_title": "Commercial Director",
			"reasoning": "Mid-size company - commercial director typically owns aftermarket",
		}
	return {
		"suggested_title": "General Manager / Sales Director",
		"reasoning": "SME - general manager or sales director likely owns all commercial decisions",
	}


SYSTEM_PROMPT = (
	"You are an executive finder agent for trade show preparation. "
	"Your goal is to find the real name and title of the best person to approach at a company booth - ideally someone in "
	"aftermarket, service, sales, or commercial roles.\n\n"
	"CRITICAL RULES:\n"
	"- Never invent, guess, or fabricate a person's name.\n"
	"- Only return a name if a tool actually returned it.\n"
	"- If no real name is found after trying all tools, return name as null.\n\n"
	"Steps:\n"
	"1. Call scrape_leadership_page with the company domain. "
	"If it returns at least one person, pick the best match for aftermarket/service/sales focus and stop - do not call any more tools.\n"
	"2. If step 1 returns an empty list, call search_person_linkedin with the company name and the provided generic title keywords. "
	"If results come back, pick the best match and stop.\n"
	"3. If both tools returned nothing, set name to null.\n\n"
	"Return a JSON object with exactly these fields: name, title, linkedin_url, source. "
	"source must be one of: website, linkedin_search, none"
)


def _extract_json_dict(text: Any) -> dict[str, Any]:
	raw = str(text or "").strip()
	if not raw:
		return {}
	if raw.startswith("```"):
		raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
		raw = re.sub(r"\s*```$", "", raw)
	try:
		parsed = json.loads(raw)
		return parsed if isinstance(parsed, dict) else {}
	except Exception:
		start = raw.find("{")
		end = raw.rfind("}")
		if start != -1 and end != -1 and end > start:
			try:
				parsed = json.loads(raw[start : end + 1])
				return parsed if isinstance(parsed, dict) else {}
			except Exception:
				return {}
	return {}


def build_people_agent() -> dict[str, Any] | None:
	if not HAS_LANGCHAIN:
		return None

	llm = None
	try:
		if GEMINI_API_KEY:
			llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, google_api_key=GEMINI_API_KEY, temperature=0)
		elif GROQ_API_KEY:
			llm = ChatGroq(model=GROQ_MODEL, groq_api_key=GROQ_API_KEY, temperature=0)
	except Exception as exc:
		logger.warning("People agent LLM init failed: %s", exc)
		return None

	if llm is None:
		return None

	tools = [scrape_leadership_page, search_person_linkedin]
	return {"llm": llm.bind_tools(tools), "tools": {t.name: t for t in tools}, "system_prompt": SYSTEM_PROMPT}


def _process_people_tool_calls(
	agent: dict[str, Any],
	tool_calls: list[dict[str, Any]],
	messages: list[Any],
	call_count: int,
) -> tuple[int, bool]:
	remaining = 2 - call_count
	if remaining <= 0:
		return (call_count, False)

	for tool_call in tool_calls[:remaining]:
		call_count += 1
		tool_name = tool_call.get("name", "")
		args = tool_call.get("args", {}) if isinstance(tool_call.get("args", {}), dict) else {}
		tool_obj = agent["tools"].get(tool_name)
		try:
			result = tool_obj.invoke(args) if tool_obj is not None else []
		except Exception as exc:
			logger.warning("People agent tool %s failed: %s", tool_name, exc)
			result = []
		messages.append(ToolMessage(content=json.dumps(result, ensure_ascii=True, default=str), tool_call_id=tool_call.get("id", "")))

	return (call_count, len(tool_calls) <= remaining)


def _invoke_people_agent(agent: dict[str, Any], prompt_input: str) -> dict[str, Any]:
	messages = [
		SystemMessage(content=agent["system_prompt"]),
		HumanMessage(content=prompt_input),
	]

	call_count = 0
	for _ in range(6):
		ai_message = agent["llm"].invoke(messages)
		tool_calls = getattr(ai_message, "tool_calls", None) or []
		if not tool_calls:
			return _extract_json_dict(getattr(ai_message, "content", ""))

		messages.append(ai_message)
		call_count, ok = _process_people_tool_calls(agent, tool_calls, messages, call_count)
		if not ok:
			return {}

	return {}


def find_key_person(
	company_name: str,
	resolved_domain: str,
	aftermarket_data: dict,
	enrichment_data: dict,
) -> dict:
	safe_default = {
		"name": None,
		"title": None,
		"linkedin_url": None,
		"source": "none",
	}

	try:
		agent = build_people_agent()
		if agent is None:
			return safe_default

		prompt_input = (
			f"Company: {company_name}\n"
			f"Domain: {resolved_domain}\n"
			f"Title keywords to search for: {DEFAULT_TITLE_KEYWORDS}\n"
			"Find a real person matching or close to these roles."
		)

		raw = _invoke_people_agent(agent, prompt_input)
		if not isinstance(raw, dict):
			return safe_default

		name = raw.get("name")
		title = raw.get("title")
		linkedin_url = raw.get("linkedin_url")
		source = raw.get("source") if raw.get("source") in {"website", "linkedin_search", "none"} else "none"

		# Hard rule: if we don't have a tool-backed plausible person name, return null.
		if not isinstance(name, str) or not _is_likely_person_name(name) or _name_looks_like_company(name):
			name = None
			if source != "none":
				source = "none"

		return {
			"name": name,
			"title": title if isinstance(title, str) and title.strip() else None,
			"linkedin_url": linkedin_url if isinstance(linkedin_url, str) and linkedin_url.strip() else None,
			"source": source,
		}
	except Exception as exc:
		logger.warning("find_key_person failed for %s: %s", company_name, exc)
		return safe_default
