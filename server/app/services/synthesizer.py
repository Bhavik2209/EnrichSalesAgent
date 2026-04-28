from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import re
import time
from typing import Any, Callable
from urllib.parse import urlparse

from app.cache import get_cached_research_response, set_cached_research_response
from app.config import GROQ_API_KEY
from app.llms import (
	HAS_LLM,
	OPENING_LINE_PRIMARY_GROQ_MODEL,
	OPENING_LINE_SECONDARY_GROQ_MODEL,
	build_default_json_llm,
	build_groq_llm,
)
from app.models import ResearchResponse
from app.prompts import build_opening_line_prompt, build_synthesis_prompt
from app.services.aftermarket import detect_aftermarket
from app.services.discovery import parse_wikidata_company, resolve_official_domain
from app.services.discovery import _is_suspicious_official_domain as is_suspicious_official_domain
from app.services.enrichment import enrich_company
from app.services.geography import classify_hq_geography
from app.services.people import find_key_person
from app.services.scraper import extract_what_they_make_from_text as extract_what_they_make
from app.services.scraper import get_about_page_text

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[str, str, str, dict[str, Any] | None], None]

WIKIDATA_PRIORITY_FIELDS = {
	"official_name",
	"founded_year",
	"hq_city",
	"hq_country",
	"parent_company",
	"industry",
}

INTERNAL_DATA_KEYS = {
	"_hq_entity_id",
	"_country_entity_id",
	"_parent_entity_id",
	"_industry_entity_id",
}

def _log_timing(company_name: str, stage: str, started_at: float) -> float:
	elapsed = time.perf_counter() - started_at
	message = f"[timing] company={company_name} stage={stage} took {elapsed:.2f}s"
	logger.info(message)
	return elapsed


def _emit_progress(
	progress_cb: ProgressCallback | None,
	stage: str,
	status: str,
	message: str,
	data: dict[str, Any] | None = None,
) -> None:
	if progress_cb is None:
		return
	try:
		progress_cb(stage, status, message, data)
	except Exception:
		pass


def _timed_call(company_name: str, stage: str, func: Any, *args: Any) -> Any:
	started_at = time.perf_counter()
	try:
		return func(*args)
	finally:
		_log_timing(company_name, stage, started_at)


def _is_empty(value: Any) -> bool:
	if value is None:
		return True
	if isinstance(value, str):
		return value.strip() == ""
	return False


def _is_weak_description(value: Any) -> bool:
	text = re.sub(r"\s+", " ", str(value or "")).strip().strip(".").lower()
	if not text:
		return True

	generic_exact = {
		"company",
		"corporation",
		"manufacturer",
		"business",
		"enterprise",
		"organization",
	}
	if text in generic_exact:
		return True

	if re.fullmatch(r"(?:[a-z]+\s+)?company", text):
		return True
	if re.fullmatch(r"(?:[a-z]+\s+)?corporation", text):
		return True
	if re.fullmatch(r"(?:[a-z]+\s+)?manufacturer", text):
		return True

	words = text.split()
	if len(words) <= 3 and any(word in {"company", "corporation", "manufacturer", "business"} for word in words):
		return True

	return False


def _source_label_for_key(source_label: Any, key: str, fallback: str) -> str:
	if isinstance(source_label, dict):
		value = source_label.get(key)
		if isinstance(value, str) and value.strip():
			return value.strip()
	if isinstance(source_label, str) and source_label.strip():
		return source_label.strip()
	return fallback


def merge_into(
	target: dict,
	source: dict,
	field_sources: dict,
	source_label: Any,
	skip_if_present: set | None = None,
) -> None:
	if not isinstance(source, dict):
		return
	skip_if_present = skip_if_present or set()

	for key, value in source.items():
		if _is_empty(value):
			continue
		if key == "description":
			if _is_weak_description(value) and not _is_empty(target.get(key)):
				continue
			if key in skip_if_present and not _is_empty(target.get(key)) and _is_weak_description(target.get(key)):
				target[key] = value
				field_sources[key] = _source_label_for_key(source_label, key, "unknown")
				continue
		if key in skip_if_present and not _is_empty(target.get(key)):
			continue
		target[key] = value
		field_sources[key] = _source_label_for_key(source_label, key, "unknown")


def _extract_json_obj(raw: Any) -> dict[str, Any]:
	text = str(raw or "").strip()
	if not text:
		return {}
	if text.startswith("```"):
		text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
		text = re.sub(r"\s*```$", "", text)
	try:
		parsed = json.loads(text)
		return parsed if isinstance(parsed, dict) else {}
	except Exception:
		start = text.find("{")
		end = text.rfind("}")
		if start >= 0 and end > start:
			try:
				parsed = json.loads(text[start : end + 1])
				return parsed if isinstance(parsed, dict) else {}
			except Exception:
				return {}
	return {}


def _normalize_domain_url(domain: str | None) -> str | None:
	if not domain:
		return None
	raw = str(domain).strip()
	if not raw:
		return None
	if not raw.startswith("http"):
		raw = f"https://{raw}"
	parsed = urlparse(raw)
	host = parsed.netloc or parsed.path
	if not host:
		return None
	return f"https://{host.strip('/') }"


def _clean_for_sentence(value: Any, max_len: int = 160) -> str:
	text = re.sub(r"\s+", " ", str(value or "")).strip()
	text = text.rstrip(" .")
	return text[:max_len].strip()


def _search_result_description_fallback(resolved_domain: str | None, search_results: Any) -> str | None:
	if not isinstance(search_results, list):
		return None

	resolved_host = ""
	resolved_root = ""
	if resolved_domain:
		normalized = _normalize_domain_url(resolved_domain)
		if normalized:
			parsed = urlparse(normalized)
			resolved_host = parsed.netloc.lower()
			resolved_root = normalized.rstrip("/").lower()

	best_snippet = None
	best_score = -1
	for item in search_results:
		if not isinstance(item, dict):
			continue
		snippet = _clean_for_sentence(item.get("snippet"), max_len=220)
		if _is_empty(snippet) or _is_weak_description(snippet):
			continue
		score = len(snippet)
		url = str(item.get("url") or "").strip()
		url_l = url.lower()
		parsed_url = urlparse(url if url.startswith("http") else f"https://{url}")
		path = parsed_url.path or "/"
		if resolved_host and resolved_host in url:
			score += 200
		if resolved_root and url_l.rstrip("/") == resolved_root:
			score += 300
		if path in {"", "/"}:
			score += 120
		else:
			score -= min(len(path), 120)
		if any(keyword in snippet.lower() for keyword in ("manufacturer", "manufacture", "provides", "offers", "automation", "pneumatic", "products")):
			score += 180
		if len(snippet) > 40 and score > best_score:
			best_snippet = snippet
			best_score = score

	return best_snippet


def _build_opening_line(company_name: str, data: dict[str, Any]) -> str | None:
	recent_news = data.get("recent_news", [])
	if isinstance(recent_news, list):
		for item in recent_news:
			if not isinstance(item, dict):
				continue
			title = _clean_for_sentence(item.get("title"), max_len=140)
			if title:
				return f"I saw {company_name} in the news around {title}, and I wanted to hear how that connects to your service and aftermarket priorities this year."

	what_they_make = _clean_for_sentence(data.get("what_they_make"), max_len=90)
	if what_they_make:
		return f"I saw that {company_name} makes {what_they_make}, and I’d love to hear how you’re thinking about service, support, and aftermarket growth around that portfolio."

	description = _clean_for_sentence(data.get("description"), max_len=120)
	if description and not _is_weak_description(description):
		return f"I noticed that {company_name} is focused on {description.lower()}, and I’d love to hear where service and digital transformation are landing for your team right now."

	return None


def _normalize_opening_line_candidate(raw: Any, company_name: str) -> str | None:
	if isinstance(raw, dict):
		raw = raw.get("personalized_opening_line")
	text = re.sub(r"\s+", " ", str(raw or "")).strip().strip('"').strip("'")
	if not text:
		return None
	if not text.endswith((".", "?", "!")):
		text = f"{text}."
	lower = text.lower()
	rejected_fragments = (
		"united states manufacturing company",
		"is focused on",
		"leading company",
		"great company",
		"i noticed that",
	)
	if any(fragment in lower for fragment in rejected_fragments):
		return None
	if company_name.lower() not in lower:
		return None
	if len(text.split()) < 12:
		return None
	return text


def _invoke_groq_model(prompt: str, model_name: str) -> dict[str, Any]:
	if not (HAS_LLM and GROQ_API_KEY):
		return {}
	llm = build_groq_llm(model=model_name, temperature=0)
	if llm is None:
		return {}
	response = llm.invoke(prompt)
	return _extract_json_obj(getattr(response, "content", ""))


def _invoke_opening_line_groq_model(prompt: str, company_name: str, model_name: str) -> str | None:
	return _normalize_opening_line_candidate(_invoke_groq_model(prompt, model_name), company_name)


def generate_opening_line_with_llms(company_name: str, data: dict[str, Any]) -> tuple[str | None, str | None]:
	if not HAS_LLM:
		return (None, None)

	prompt_data = {
		"official_name": _clean_for_sentence(data.get("official_name"), max_len=120) or None,
		"description": _clean_for_sentence(data.get("description"), max_len=180) or None,
		"industry": _clean_for_sentence(data.get("industry"), max_len=120) or None,
		"what_they_make": _clean_for_sentence(data.get("what_they_make"), max_len=120) or None,
		"hq_country": _clean_for_sentence(data.get("hq_country"), max_len=80) or None,
		"hq_city": _clean_for_sentence(data.get("hq_city"), max_len=80) or None,
		"parent_company": _clean_for_sentence(data.get("parent_company"), max_len=120) or None,
		"aftermarket_footprint": _clean_for_sentence(data.get("aftermarket_footprint"), max_len=120) or None,
	}
	prompt = build_opening_line_prompt(company_name, prompt_data)
	candidates: list[tuple[str, str]] = []
	for model_name in dict.fromkeys([OPENING_LINE_PRIMARY_GROQ_MODEL, OPENING_LINE_SECONDARY_GROQ_MODEL]):
		if model_name:
			candidates.append((f"groq:{model_name}", model_name))
	if not candidates:
		return (None, None)

	try:
		with concurrent.futures.ThreadPoolExecutor(max_workers=len(candidates)) as executor:
			future_map = {
				executor.submit(_invoke_opening_line_groq_model, prompt, company_name, model_name): provider
				for provider, model_name in candidates
			}
			for future in concurrent.futures.as_completed(future_map):
				provider = future_map[future]
				try:
					line = future.result()
				except Exception as exc:
					logger.warning("Opening line generation failed with %s for %s: %s", provider, company_name, exc)
					continue
				if line:
					return (line, provider)
	except Exception as exc:
		logger.warning("Parallel opening line generation failed for %s: %s", company_name, exc)

	return (None, None)


def _run_sync_or_async_in_thread(func: Any, *args: Any) -> Any:
	result = func(*args)
	if asyncio.iscoroutine(result):
		return asyncio.run(result)
	return result


def _invoke_gemini(prompt: str) -> dict[str, Any]:
	llm = build_default_json_llm(temperature=0)
	if llm is None:
		return {}
	response = llm.invoke(prompt)
	return _extract_json_obj(getattr(response, "content", ""))


def _invoke_groq(prompt: str) -> dict[str, Any]:
	if not (HAS_LLM and GROQ_API_KEY):
		return {}
	llm = build_groq_llm(temperature=0)
	if llm is None:
		return {}
	response = llm.invoke(prompt)
	return _extract_json_obj(getattr(response, "content", ""))


def run_llm_synthesis(
	company_name: str,
	missing_fields: list[str],
	about_text: str,
	wikidata_description: str,
) -> dict:
	if not missing_fields:
		return {}

	combined_text = f"{about_text or ''}\n{wikidata_description or ''}".strip()
	if not combined_text:
		return {}

	prompt = build_synthesis_prompt(company_name, missing_fields, combined_text)
	try:
		result = _invoke_gemini(prompt)
		if not result:
			result = _invoke_groq(prompt)
		if not isinstance(result, dict):
			return {}
		return {field: result.get(field) for field in missing_fields if field in result and not _is_empty(result.get(field))}
	except Exception as exc:
		logger.warning("run_llm_synthesis failed for %s: %s", company_name, exc)
		return {}


async def _step1_discovery(company_name: str, extra_context: str, notes: list[str], sources: list[str], data: dict[str, Any], field_sources: dict[str, str], progress_cb: ProgressCallback | None = None) -> tuple[str | None, dict[str, Any]]:
	resolved_domain: str | None = None
	wikidata: dict[str, Any] = {}
	try:
		_emit_progress(progress_cb, "discovery.start", "info", "Resolving official website and Wikidata profile")
		domain_result, wikidata_result = await asyncio.gather(
			asyncio.to_thread(_run_sync_or_async_in_thread, resolve_official_domain, company_name, extra_context),
			asyncio.to_thread(_run_sync_or_async_in_thread, parse_wikidata_company, company_name),
			return_exceptions=True,
		)
		if isinstance(domain_result, Exception):
			notes.append(f"Domain discovery failed: {domain_result}")
		else:
			try:
				resolved_domain, search_results = domain_result
			except Exception as exc:
				notes.append(f"Domain discovery parse failed: {exc}")
				search_results = []

		if isinstance(wikidata_result, Exception):
			notes.append(f"Wikidata lookup failed: {wikidata_result}")
		else:
			wikidata = wikidata_result if isinstance(wikidata_result, dict) else {}

		if not resolved_domain and wikidata.get("website"):
			resolved_domain = str(wikidata.get("website"))
			notes.append("Used Wikidata website as resolved domain fallback")
			_emit_progress(progress_cb, "discovery.domain", "fallback", "Used Wikidata website as the resolved domain fallback")
		elif is_suspicious_official_domain(resolved_domain) and wikidata.get("website"):
			resolved_domain = str(wikidata.get("website"))
			notes.append("Replaced suspicious resolved domain with Wikidata website")
			_emit_progress(progress_cb, "discovery.domain", "fallback", "Replaced a suspicious domain candidate with the Wikidata website")

		merge_into(data, wikidata, field_sources, "wikidata", skip_if_present=set())
		if _is_weak_description(data.get("description")):
			search_description = _search_result_description_fallback(resolved_domain, search_results)
			if search_description:
				data["description"] = search_description
				field_sources["description"] = "discovery_search_snippet"
				_emit_progress(progress_cb, "discovery.description", "fallback", "Used a search snippet as a temporary description fallback")
		if wikidata.get("wikidata_url"):
			sources.append(str(wikidata.get("wikidata_url")))
		_emit_progress(progress_cb, "discovery.complete", "completed", "Discovery complete", {"resolved_domain": resolved_domain or ""})
	except Exception as exc:
		notes.append(f"Discovery step failed: {exc}")
	return (resolved_domain, wikidata)


def _merge_enrichment_fields(data: dict[str, Any], field_sources: dict[str, str], enrichment_data: dict[str, Any], enrich_sources: dict[str, str]) -> None:
	for field in ["employee_count", "revenue"]:
		value = enrichment_data.get(field)
		if _is_empty(value):
			continue
		data[field] = value
		field_sources[field] = _source_label_for_key(enrich_sources, field, "enrichment")

	for field_name, value in enrichment_data.items():
		if _is_empty(value):
			continue
		if _source_label_for_key(enrich_sources, field_name, "") != "hunter_company_profile":
			continue
		data[field_name] = value
		field_sources[field_name] = "hunter_company_profile"

	merge_into(
		data,
		enrichment_data,
		field_sources,
		enrich_sources or "enrichment",
		skip_if_present=WIKIDATA_PRIORITY_FIELDS,
	)


def _preserve_hunter_aftermarket_signal(data: dict[str, Any], aftermarket_data: dict[str, Any]) -> dict[str, Any]:
	if not isinstance(aftermarket_data, dict):
		return {}

	if data.get("aftermarket_footprint") is True:
		patched = dict(aftermarket_data)
		patched.pop("aftermarket_footprint", None)
		patched.pop("aftermarket_reason", None)
		return patched

	return aftermarket_data


def _has_hunter_description(enrichment_data: dict[str, Any], enrich_sources: dict[str, str]) -> bool:
	description = enrichment_data.get("description")
	return (
		not _is_empty(description)
		and not _is_weak_description(description)
		and _source_label_for_key(enrich_sources, "description", "") == "hunter_company_profile"
	)


def _has_hunter_aftermarket_signal(enrichment_data: dict[str, Any], enrich_sources: dict[str, str]) -> bool:
	return (
		enrichment_data.get("aftermarket_footprint") is True
		and _source_label_for_key(enrich_sources, "aftermarket_footprint", "") == "hunter_company_profile"
	)


def _derive_what_they_make_from_tags(tags: Any) -> str | None:
	if not isinstance(tags, list):
		return None

	clean_tags = [
		re.sub(r"\s+", " ", str(tag or "")).strip()
		for tag in tags
		if isinstance(tag, str) and str(tag).strip()
	]
	if not clean_tags:
		return None

	generic = {
		"manufacturing",
		"automation",
		"supply chain",
		"production efficiency",
		"it solutions",
	}
	preferred = [tag for tag in clean_tags if tag.lower() not in generic]
	selected = preferred[:4] if preferred else clean_tags[:4]
	if not selected:
		return None
	if len(selected) == 1:
		return selected[0]
	if len(selected) == 2:
		return f"{selected[0]} and {selected[1]}"
	return f"{', '.join(selected[:-1])}, and {selected[-1]}"


def _apply_hq_geography(data: dict[str, Any], field_sources: dict[str, str]) -> None:
	geography = classify_hq_geography(data.get("hq_country"))
	for key, value in geography.items():
		if _is_empty(value):
			continue
		data[key] = value
		field_sources[key] = "hq_geography_classifier"


def _unpack_enrichment_result(enrich_result: Any, notes: list[str]) -> tuple[dict[str, Any], dict[str, str]]:
	if isinstance(enrich_result, Exception):
		notes.append(f"Enrichment failed: {enrich_result}")
		return ({}, {})
	try:
		enrichment_data, enrich_sources = enrich_result
		return (
			enrichment_data if isinstance(enrichment_data, dict) else {},
			enrich_sources if isinstance(enrich_sources, dict) else {},
		)
	except Exception as exc:
		notes.append(f"Enrichment unpack failed: {exc}")
		return ({}, {})


def _unpack_scraper_result(scraper_result: Any, notes: list[str]) -> tuple[dict[str, Any], str, str]:
	scraper_label = "failed"
	if isinstance(scraper_result, Exception):
		notes.append(f"Scraper failed: {scraper_result}")
		return ({}, scraper_label, "")
	try:
		scraper_dict, scraper_label = scraper_result
		safe_dict = scraper_dict if isinstance(scraper_dict, dict) else {}
		about_text = str(safe_dict.get("description", "") or "")
		return (safe_dict, scraper_label, about_text)
	except Exception as exc:
		notes.append(f"Scraper unpack failed: {exc}")
		return ({}, "failed", "")


def _unpack_news_result(news_result: Any, notes: list[str]) -> list[dict[str, Any]]:
	if isinstance(news_result, Exception):
		notes.append(f"News lookup failed: {news_result}")
		return []
	if not isinstance(news_result, list):
		return []
	return [item for item in news_result if isinstance(item, dict)]


async def _step2_parallel_services(
	company_name: str,
	resolved_domain: str | None,
	wikidata: dict[str, Any],
	notes: list[str],
	sources: list[str],
	data: dict[str, Any],
	field_sources: dict[str, str],
	progress_cb: ProgressCallback | None = None,
) -> tuple[dict[str, Any], dict[str, str], dict[str, Any], str]:
	enrichment_data: dict[str, Any] = {}
	enrich_sources: dict[str, str] = {}
	scraper_dict: dict[str, Any] = {}
	aftermarket_data: dict[str, Any] = {}
	about_text = ""

	try:
		_emit_progress(progress_cb, "enrichment.start", "info", "Fetching company profile and enrichment providers")
		enrich_result = await asyncio.to_thread(
			_timed_call,
			company_name,
			"step2.enrich_company",
			enrich_company,
			company_name,
			resolved_domain,
			wikidata,
			progress_cb,
		)
		enrichment_data, enrich_sources = _unpack_enrichment_result(enrich_result, notes)

		_merge_enrichment_fields(data, field_sources, enrichment_data, enrich_sources)

		needs_scraper = not _has_hunter_description(enrichment_data, enrich_sources)
		needs_aftermarket_detector = not _has_hunter_aftermarket_signal(enrichment_data, enrich_sources)

		async_calls: list[Any] = []
		call_names: list[str] = []
		if needs_scraper:
			async_calls.append(
				asyncio.to_thread(
					_timed_call,
					company_name,
					"step2.get_about_page_text",
					get_about_page_text,
					resolved_domain or "",
					str(wikidata.get("website") or ""),
					progress_cb,
				)
			)
			call_names.append("scraper")
		else:
			notes.append("Skipped website description scrape because Hunter already provided a usable description")
			_emit_progress(progress_cb, "scraper", "skipped", "Skipping website scrape because Hunter already provided a usable description")

		if needs_aftermarket_detector:
			async_calls.append(
				asyncio.to_thread(
					_timed_call,
					company_name,
					"step2.detect_aftermarket",
					detect_aftermarket,
					resolved_domain or "",
					str(wikidata.get("website") or ""),
				)
			)
			call_names.append("aftermarket")
		else:
			notes.append("Skipped website aftermarket detection because Hunter already provided positive aftermarket evidence")
			_emit_progress(progress_cb, "aftermarket", "skipped", "Skipping website aftermarket detection because Hunter already provided positive aftermarket evidence")

		if async_calls:
			async_results = await asyncio.gather(*async_calls, return_exceptions=True)
			for call_name, call_result in zip(call_names, async_results):
				if call_name == "scraper":
					scraper_dict, scraper_label, about_text = _unpack_scraper_result(call_result, notes)
					_emit_progress(progress_cb, "scraper", "completed", f"Website profile scrape completed via {scraper_label}")
					merge_into(data, scraper_dict, field_sources, scraper_label, skip_if_present={"description"})
					if scraper_dict.get("source_url"):
						sources.append(str(scraper_dict.get("source_url")))
				elif call_name == "aftermarket":
					if isinstance(call_result, Exception):
						notes.append(f"Aftermarket detection failed: {call_result}")
					elif isinstance(call_result, dict):
						aftermarket_data = call_result
						_emit_progress(progress_cb, "aftermarket", "completed", "Website aftermarket analysis completed")
						merge_into(
							data,
							_preserve_hunter_aftermarket_signal(data, aftermarket_data),
							field_sources,
							"aftermarket_detector",
							skip_if_present=set(),
						)
						for aftermarket_key in ("parts_page", "service_page", "support_page", "customer_portal_page"):
							if isinstance(aftermarket_data.get(aftermarket_key), str) and aftermarket_data.get(aftermarket_key):
								sources.append(str(aftermarket_data.get(aftermarket_key)))

		if _is_empty(data.get("what_they_make")):
			tags_based = _derive_what_they_make_from_tags(enrichment_data.get("company_tags"))
			if tags_based:
				data["what_they_make"] = tags_based
				field_sources["what_they_make"] = "hunter_tags"
				about_text = about_text or str(enrichment_data.get("description") or "")
				_emit_progress(progress_cb, "what_they_make", "fallback", "Derived what the company makes from Hunter tags")
	except Exception as exc:
		notes.append(f"Parallel service step failed: {exc}")

	return (enrichment_data, enrich_sources, scraper_dict, about_text)


async def _step3_sequential(
	company_name: str,
	resolved_domain: str | None,
	aftermarket_data: dict[str, Any],
	enrichment_data: dict[str, Any],
	about_text: str,
	data: dict[str, Any],
	field_sources: dict[str, str],
	progress_cb: ProgressCallback | None = None,
) -> None:
	try:
		if resolved_domain:
			try:
				_emit_progress(progress_cb, "people.start", "info", "Finding the best booth contact")
				people_result = await asyncio.to_thread(
					_timed_call,
					company_name,
					"step3.find_key_person",
					find_key_person,
					company_name,
					resolved_domain,
					aftermarket_data,
					enrichment_data,
					progress_cb,
				)
				if isinstance(people_result, dict):
					person_mapping = {
						"name": "target_person_name",
						"title": "target_person_title",
						"linkedin_url": "target_person_linkedin_url",
						"email": "target_person_email",
						"confidence": "target_person_confidence",
						"source": "target_person_source",
						"suggested_title": "suggested_target_title",
						"suggested_title_reasoning": "suggested_target_title_reasoning",
					}
					for src_key, dst_key in person_mapping.items():
						value = people_result.get(src_key)
						if _is_empty(value):
							continue
						data[dst_key] = value
						field_sources[dst_key] = "people_service"
					if people_result.get("name") or people_result.get("title"):
						_emit_progress(progress_cb, "people.complete", "completed", "Contact targeting completed")
			except Exception:
				pass

		if _is_empty(data.get("what_they_make")) and about_text:
			try:
				_emit_progress(progress_cb, "what_they_make", "info", "Extracting what the company makes from profile text")
				wtm = await asyncio.to_thread(
					_timed_call,
					company_name,
					"step3.extract_what_they_make",
					extract_what_they_make,
					about_text,
				)
				if not _is_empty(wtm):
					data["what_they_make"] = wtm
					field_sources["what_they_make"] = "scraper_regex"
					_emit_progress(progress_cb, "what_they_make", "completed", "Extracted what the company makes from profile text")
			except Exception:
				pass
		if _is_empty(data.get("personalized_opening_line")):
			llm_opening_line = None
			llm_provider = None
			try:
				_emit_progress(progress_cb, "opening_line", "info", "Generating a personalized opening line")
				llm_opening_line, llm_provider = await asyncio.to_thread(
					generate_opening_line_with_llms,
					company_name,
					data,
				)
			except Exception:
				llm_opening_line, llm_provider = (None, None)
			opening_line = llm_opening_line or _build_opening_line(company_name, data)
			if opening_line:
				data["personalized_opening_line"] = opening_line
				field_sources["personalized_opening_line"] = (
					f"opening_line_llm_{llm_provider}" if llm_opening_line and llm_provider else "opening_line_generator"
				)
				_emit_progress(progress_cb, "opening_line", "completed", "Opening line ready")
	except Exception:
		pass


def _step5_collect_sources(
	resolved_domain: str | None,
	wikidata: dict[str, Any],
	scraper_dict: dict[str, Any],
	enrich_sources: dict[str, str],
	data: dict[str, Any],
	sources: list[str],
	notes: list[str],
) -> list[str]:
	def _append_if_url(value: Any) -> None:
		if isinstance(value, str) and value.strip():
			sources.append(value.strip())

	try:
		_append_if_url(wikidata.get("wikidata_url"))

		norm_domain = _normalize_domain_url(resolved_domain)
		_append_if_url(norm_domain)

		_append_if_url(scraper_dict.get("source_url"))
		_append_if_url(data.get("company_linkedin_url"))

		for news_item in data.get("recent_news", []) if isinstance(data.get("recent_news", []), list) else []:
			if isinstance(news_item, dict):
				_append_if_url(news_item.get("url"))

		for value in (enrich_sources or {}).values():
			if isinstance(value, str) and value.startswith("http"):
				sources.append(value)

		_append_if_url(data.get("target_person_linkedin_url"))

		return list(dict.fromkeys(u for u in sources if isinstance(u, str) and u.strip()))
	except Exception as exc:
		notes.append(f"Source URL collection failed: {exc}")
		return list(dict.fromkeys(u for u in sources if isinstance(u, str) and u.strip()))


def _step6_filter_requested_fields(
	requested_fields: list[str] | None,
	data: dict[str, Any],
	field_sources: dict[str, str],
	notes: list[str],
) -> tuple[dict[str, Any], dict[str, str]]:
	try:
		if not requested_fields:
			return (data, field_sources)
		requested = set(requested_fields)
		return (
			{k: v for k, v in data.items() if k in requested},
			{k: v for k, v in field_sources.items() if k in requested},
		)
	except Exception as exc:
		notes.append(f"Field filtering failed: {exc}")
		return (data, field_sources)


def _remove_internal_fields(data: dict[str, Any], field_sources: dict[str, str]) -> tuple[dict[str, Any], dict[str, str]]:
	return (
		{k: v for k, v in data.items() if k not in INTERNAL_DATA_KEYS},
		{k: v for k, v in field_sources.items() if k not in INTERNAL_DATA_KEYS},
	)


async def research_company(
	company_name: str,
	extra_context: str = "",
	requested_fields: list[str] | None = None,
	progress_cb: ProgressCallback | None = None,
) -> ResearchResponse:
	total_started_at = time.perf_counter()

	_emit_progress(progress_cb, "cache.lookup", "info", f"Checking cache for {company_name}")
	cached_payload = await asyncio.to_thread(
		get_cached_research_response,
		company_name,
		extra_context,
		requested_fields,
	)
	if isinstance(cached_payload, dict):
		_emit_progress(progress_cb, "cache.lookup", "cache_hit", "Cache hit. Returning cached research response")
		_log_timing(company_name, "total_research_cache_hit", total_started_at)
		return ResearchResponse(**cached_payload)
	_emit_progress(progress_cb, "cache.lookup", "completed", "No cache hit. Running live research")

	notes: list[str] = []
	sources: list[str] = []
	data: dict[str, Any] = {}
	field_sources: dict[str, str] = {}

	stage_started_at = time.perf_counter()
	resolved_domain, wikidata = await _step1_discovery(company_name, extra_context, notes, sources, data, field_sources, progress_cb)
	_log_timing(company_name, "step1_discovery", stage_started_at)

	stage_started_at = time.perf_counter()
	enrichment_data, enrich_sources, scraper_dict, about_text = await _step2_parallel_services(
		company_name,
		resolved_domain,
		wikidata,
		notes,
		sources,
		data,
		field_sources,
		progress_cb,
	)
	_log_timing(company_name, "step2_parallel_services", stage_started_at)
	_apply_hq_geography(data, field_sources)
	aftermarket_data = {
		"aftermarket_footprint": data.get("aftermarket_footprint"),
		"parts_page": data.get("parts_page"),
		"service_page": data.get("service_page"),
		"support_page": data.get("support_page"),
		"customer_portal_page": data.get("customer_portal_page"),
		"portal_detected": data.get("portal_detected"),
		"aftermarket_reason": data.get("aftermarket_reason"),
	}

	stage_started_at = time.perf_counter()
	await _step3_sequential(
		company_name,
		resolved_domain,
		aftermarket_data,
		enrichment_data,
		about_text,
		data,
		field_sources,
		progress_cb,
	)
	_log_timing(company_name, "step3_sequential", stage_started_at)

	stage_started_at = time.perf_counter()
	sources = _step5_collect_sources(
		resolved_domain,
		wikidata,
		scraper_dict,
		enrich_sources,
		data,
		sources,
		notes,
	)
	_log_timing(company_name, "step5_collect_sources", stage_started_at)

	stage_started_at = time.perf_counter()
	data, field_sources = _step6_filter_requested_fields(requested_fields, data, field_sources, notes)
	_log_timing(company_name, "step6_filter_requested_fields", stage_started_at)
	data, field_sources = _remove_internal_fields(data, field_sources)
	total_elapsed = _log_timing(company_name, "total_research", total_started_at)
	notes.append(f"Timing total_research={total_elapsed:.2f}s")
	_emit_progress(progress_cb, "research.complete", "completed", "Briefing complete. Returning result")

	response = ResearchResponse(
		company_name=company_name,
		resolved_domain=resolved_domain,
		data=data,
		field_sources=field_sources,
		sources=sources,
		notes=notes,
	)
	await asyncio.to_thread(
		set_cached_research_response,
		company_name,
		extra_context,
		requested_fields,
		response.model_dump(),
	)
	return response
