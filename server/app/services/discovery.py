from __future__ import annotations

import asyncio
import logging
import re
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import quote, urlparse

from bs4 import BeautifulSoup

from app.config import REQUEST_TIMEOUT, SESSION, TAVILY_API_KEY

logger = logging.getLogger(__name__)

AGGREGATOR_DOMAINS = {
	"wikipedia.org",
	"linkedin.com",
	"crunchbase.com",
	"bloomberg.com",
	"reuters.com",
	"forbes.com",
	"businesswire.com",
	"prnewswire.com",
	"glassdoor.com",
	"indeed.com",
	"zoominfo.com",
	"dnb.com",
	"manta.com",
	"facebook.com",
	"instagram.com",
	"twitter.com",
	"youtube.com",
	"reddit.com",
	"quora.com",
}

COMPANY_HINTS = {
	"company",
	"corporation",
	"manufacturer",
	"manufacturing",
	"group",
	"enterprise",
	"holding",
	"industrial",
	"industries",
	"plc",
	"ag",
	"gmbh",
	"inc",
	"ltd",
	"sa",
	"nv",
	"bv",
	"oy",
	"as",
	"co",
}


def extract_domain(url: str) -> str:
	try:
		parsed = urlparse(url)
		host = parsed.netloc or parsed.path
		host = host.split(":")[0].lower().strip()
		host = re.sub(r"^www\.", "", host)
		return host
	except Exception:
		return url.lower().strip()


def normalize_root_url(url: str) -> str:
	try:
		parsed = urlparse(url if url.startswith("http") else f"https://{url}")
		return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
	except Exception:
		return url.rstrip("/")


def score_candidate_url(url: str, company_name: str) -> float:
	domain = extract_domain(url)
	score = 0.0

	if any(agg in domain for agg in AGGREGATOR_DOMAINS):
		return -1.0

	clean_name = re.sub(r"\b(ag|corp|corporation|inc|gmbh|ltd|co|group|sa|plc|llc)\b", "", company_name.lower()).strip()
	name_token = clean_name.replace(" ", "").replace("-", "")
	domain_token = domain.replace(".", "").replace("-", "")

	if name_token and name_token in domain_token:
		score += 0.5
	else:
		similarity = SequenceMatcher(None, name_token, domain_token).ratio()
		if similarity > 0.6:
			score += 0.3
		elif similarity > 0.4:
			score += 0.1

	if domain.endswith(".com") or domain.endswith(".co") or domain.endswith(".de") or domain.endswith(".jp"):
		score += 0.1

	return score


def search_tavily(company_name: str, extra_context: str = "", max_results: int = 5) -> list[dict[str, str]]:
	if not TAVILY_API_KEY:
		return []

	query = f"{company_name} official website"
	if extra_context:
		query += f" {extra_context}"

	payload = {
		"api_key": TAVILY_API_KEY,
		"query": query,
		"max_results": max_results,
		"search_depth": "basic",
		"include_answer": False,
		"include_domains": [],
		"exclude_domains": [
			"linkedin.com",
			"facebook.com",
			"twitter.com",
			"instagram.com",
			"youtube.com",
			"glassdoor.com",
		],
	}

	try:
		response = SESSION.post("https://api.tavily.com/search", json=payload, timeout=REQUEST_TIMEOUT)
		response.raise_for_status()

		data = response.json()
		results: list[dict[str, str]] = []
		for item in data.get("results", []):
			results.append(
				{
					"url": item.get("url", ""),
					"title": item.get("title", ""),
					"snippet": item.get("content", "")[:300],
				}
			)
		return results
	except Exception as exc:
		logger.warning("Tavily search failed: %s", exc)
		return []


def search_duckduckgo(company_name: str, extra_context: str = "") -> list[dict[str, str]]:
	query = f"{company_name} official website"
	if extra_context:
		query += f" {extra_context}"
	query += " manufacturer"

	url = f"https://html.duckduckgo.com/html/?q={quote(query)}"

	try:
		response = SESSION.get(url, timeout=REQUEST_TIMEOUT)
		response.raise_for_status()

		soup = BeautifulSoup(response.text, "html.parser")
		results: list[dict[str, str]] = []
		for item in soup.select(".result__body")[:5]:
			title_el = item.select_one(".result__title")
			snippet_el = item.select_one(".result__snippet")
			link_el = item.select_one("a.result__a")
			href = link_el.get("href", "") if link_el else ""
			results.append(
				{
					"url": href,
					"title": title_el.get_text(" ", strip=True) if title_el else "",
					"snippet": snippet_el.get_text(" ", strip=True)[:300] if snippet_el else "",
				}
			)
		return results
	except Exception as exc:
		logger.warning("DuckDuckGo search failed: %s", exc)
		return []


def score_and_resolve_domain(company_name: str, results: list[dict[str, str]]) -> str | None:
	if not results:
		return None

	scored: list[tuple[float, dict[str, str]]] = []
	for result in results:
		url = result.get("url", "")
		if not url:
			continue

		score = score_candidate_url(url, company_name)
		title = result.get("title", "")
		snippet = result.get("snippet", "")
		title_lower = title.lower()
		snippet_lower = snippet.lower()
		clean_name = re.sub(r"\b(ag|corp|corporation|inc|gmbh|ltd|co|group|sa|plc|llc)\b", "", company_name.lower()).strip()

		if clean_name and clean_name in title_lower:
			score += 0.2
		elif any(token for token in clean_name.split() if len(token) > 3 and token in title_lower):
			score += 0.1

		if any(keyword in snippet_lower for keyword in ("manufacturer", "industrial", "solutions", "products", "systems")):
			score += 0.05

		scored.append((score, result))

	scored.sort(key=lambda item: item[0], reverse=True)
	best = scored[0][1] if scored and scored[0][0] > 0 else None
	return normalize_root_url(best.get("url")) if best else None


async def resolve_official_domain(company_name: str, extra_context: str = "") -> tuple[str | None, list[dict[str, str]]]:
	try:
		results = await asyncio.to_thread(search_tavily, company_name, extra_context)
		if not results:
			results = await asyncio.to_thread(search_duckduckgo, company_name, extra_context)

		resolved = await asyncio.to_thread(score_and_resolve_domain, company_name, results)
		return (resolved, results)
	except Exception as exc:
		logger.exception("Domain resolution failed for %s: %s", company_name, exc)
		return (None, [])


def search_wikidata(company_name: str) -> dict[str, Any]:
	params = {
		"action": "wbsearchentities",
		"search": company_name,
		"language": "en",
		"type": "item",
		"limit": 5,
		"format": "json",
	}

	try:
		response = SESSION.get(
			"https://www.wikidata.org/w/api.php",
			params=params,
			timeout=REQUEST_TIMEOUT,
		)
		response.raise_for_status()
		results = response.json().get("search", [])
		return _pick_best_wikidata_result(results, company_name) or {}
	except Exception as exc:
		logger.warning("Wikidata search failed: %s", exc)
		return {}


def _pick_best_wikidata_result(results: list[dict[str, Any]], company_name: str) -> dict[str, Any] | None:
	if not results:
		return None

	name_lower = company_name.lower()
	best_result = None
	best_score = -999.0

	for index, result in enumerate(results):
		score = 0.0
		label = result.get("label", "").lower()
		description = result.get("description", "").lower()

		if any(keyword in description for keyword in COMPANY_HINTS):
			score += 2.0
		if any(keyword in description for keyword in {"person", "film", "album", "book", "ship", "city", "village", "mountain"}):
			score -= 2.0

		similarity = SequenceMatcher(None, name_lower, label).ratio()
		if similarity > 0.8:
			score += 1.0
		elif similarity > 0.5:
			score += 0.5

		score -= index * 0.1

		if score > best_score:
			best_score = score
			best_result = result

	return best_result


def fetch_wikidata_entity(entity_id: str) -> dict[str, Any]:
	try:
		url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
		response = SESSION.get(url, timeout=REQUEST_TIMEOUT)
		response.raise_for_status()
		return response.json()
	except Exception as exc:
		logger.warning("Wikidata entity fetch failed for %s: %s", entity_id, exc)
		return {}


def resolve_wikidata_labels(entity_ids: list[str]) -> dict[str, str]:
	if not entity_ids:
		return {}

	params = {
		"action": "wbgetentities",
		"ids": "|".join(entity_ids),
		"props": "labels",
		"languages": "en",
		"format": "json",
	}
	try:
		response = SESSION.get(
			"https://www.wikidata.org/w/api.php",
			params=params,
			timeout=REQUEST_TIMEOUT,
		)
		response.raise_for_status()
		entities = response.json().get("entities", {})
		labels: dict[str, str] = {}
		for entity_id, entity_data in entities.items():
			label = entity_data.get("labels", {}).get("en", {}).get("value")
			if label:
				labels[entity_id] = label
		return labels
	except Exception as exc:
		logger.warning("Wikidata label resolution failed: %s", exc)
		return {}


def _first_claim_value(claims: dict[str, Any], prop: str, path: tuple[str, ...]) -> Any:
	claim_list = claims.get(prop) or []
	if not claim_list:
		return None

	value: Any = claim_list[0]
	try:
		for key in path:
			value = value[key]
		return value
	except Exception:
		return None


def _extract_wikidata_scalar_fields(entity: dict[str, Any], claims: dict[str, Any]) -> dict[str, Any]:
	result: dict[str, Any] = {}

	official_name = entity.get("labels", {}).get("en", {}).get("value")
	if official_name:
		result["official_name"] = official_name

	description = entity.get("descriptions", {}).get("en", {}).get("value")
	if description:
		result["description"] = description

	website = _first_claim_value(claims, "P856", ("mainsnak", "datavalue", "value"))
	if website:
		result["website"] = website

	time_value = _first_claim_value(claims, "P571", ("mainsnak", "datavalue", "value", "time"))
	if isinstance(time_value, str) and len(time_value) >= 5:
		result["founded_year"] = time_value[1:5]

	amount_value = _first_claim_value(claims, "P1128", ("mainsnak", "datavalue", "value", "amount"))
	if isinstance(amount_value, str):
		result["employee_count"] = amount_value.lstrip("+")

	revenue_value = _first_claim_value(claims, "P2139", ("mainsnak", "datavalue", "value", "amount"))
	if isinstance(revenue_value, str):
		result["revenue"] = revenue_value.lstrip("+")

	return result


def _extract_wikidata_reference_fields(claims: dict[str, Any]) -> dict[str, Any]:
	ref_specs = {
		"P159": ("_hq_entity_id", "hq_city"),
		"P17": ("_country_entity_id", "hq_country"),
		"P749": ("_parent_entity_id", "parent_company"),
		"P452": ("_industry_entity_id", "industry"),
	}

	result: dict[str, Any] = {}
	lookup_ids: list[str] = []

	for prop, (entity_key, _) in ref_specs.items():
		ref_id = _first_claim_value(claims, prop, ("mainsnak", "datavalue", "value", "id"))
		if ref_id:
			result[entity_key] = ref_id
			lookup_ids.append(ref_id)

	labels_map = resolve_wikidata_labels(lookup_ids)
	for entity_key, output_key in ref_specs.values():
		ref_id = result.get(entity_key)
		if ref_id and ref_id in labels_map:
			result[output_key] = labels_map[ref_id]

	return result


def _parse_wikidata_company_sync(company_name: str) -> dict[str, Any]:
	best = search_wikidata(company_name)
	if not best:
		return {}

	entity_id = best.get("id")
	if not entity_id:
		return {}

	data = fetch_wikidata_entity(entity_id)
	if not data:
		return {}

	entity = data.get("entities", {}).get(entity_id, {})
	claims = entity.get("claims", {})
	result: dict[str, Any] = {
		"wikidata_id": entity_id,
		"wikidata_url": f"https://www.wikidata.org/wiki/{entity_id}",
	}

	result.update(_extract_wikidata_scalar_fields(entity, claims))
	result.update(_extract_wikidata_reference_fields(claims))
	return result


async def parse_wikidata_company(company_name: str) -> dict[str, Any]:
	try:
		return await asyncio.to_thread(_parse_wikidata_company_sync, company_name)
	except Exception as exc:
		logger.exception("Wikidata parse failed for %s: %s", company_name, exc)
		return {}

