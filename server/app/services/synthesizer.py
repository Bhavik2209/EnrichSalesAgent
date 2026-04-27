from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any
from urllib.parse import urlparse

from app.config import GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL
from app.models import ResearchResponse
from app.services.aftermarket import detect_aftermarket
from app.services.discovery import parse_wikidata_company, resolve_official_domain
from app.services.enrichment import enrich_company
from app.services.news import find_recent_news
from app.services.scraper import extract_what_they_make_from_text as extract_what_they_make
from app.services.scraper import get_about_page_text

logger = logging.getLogger(__name__)

try:
	from langchain_groq import ChatGroq  # type: ignore[import-not-found]
	from langchain_google_genai import ChatGoogleGenerativeAI

	HAS_LLM = True
except Exception:
	ChatGoogleGenerativeAI = ChatGroq = None  # type: ignore[assignment]
	HAS_LLM = False


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
	print(message)
	logger.info(message)
	return elapsed


def _is_empty(value: Any) -> bool:
	if value is None:
		return True
	if isinstance(value, str):
		return value.strip() == ""
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
	if description:
		return f"I noticed that {company_name} is focused on {description.lower()}, and I’d love to hear where service and digital transformation are landing for your team right now."

	return None


def _run_sync_or_async_in_thread(func: Any, *args: Any) -> Any:
	result = func(*args)
	if asyncio.iscoroutine(result):
		return asyncio.run(result)
	return result


def _build_llm_prompt(company_name: str, missing_fields: list[str], combined_text: str) -> str:
	return (
		"You are extracting company information. Using only the text below,\n"
		"fill in the missing fields. Return valid JSON only, no markdown.\n"
		"If a field cannot be determined from the text, return null for it.\n\n"
		f"Company: {company_name}\n"
		f"Missing fields to fill: {missing_fields}\n\n"
		"SOURCE TEXT:\n"
		f"{combined_text[:6000]}"
	)


def _invoke_gemini(prompt: str) -> dict[str, Any]:
	if not (HAS_LLM and GEMINI_API_KEY):
		return {}
	llm = ChatGoogleGenerativeAI(
		model=GEMINI_MODEL,
		google_api_key=GEMINI_API_KEY,
		temperature=0,
		model_kwargs={"response_mime_type": "application/json"},
	)
	response = llm.invoke(prompt)
	return _extract_json_obj(getattr(response, "content", ""))


def _invoke_groq(prompt: str) -> dict[str, Any]:
	if not (HAS_LLM and GROQ_API_KEY):
		return {}
	llm = ChatGroq(model=GROQ_MODEL, groq_api_key=GROQ_API_KEY, temperature=0)
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

	prompt = _build_llm_prompt(company_name, missing_fields, combined_text)
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


async def _step1_discovery(company_name: str, extra_context: str, notes: list[str], sources: list[str], data: dict[str, Any], field_sources: dict[str, str]) -> tuple[str | None, dict[str, Any]]:
	resolved_domain: str | None = None
	wikidata: dict[str, Any] = {}
	try:
		domain_result, wikidata_result = await asyncio.gather(
			asyncio.to_thread(_run_sync_or_async_in_thread, resolve_official_domain, company_name, extra_context),
			asyncio.to_thread(_run_sync_or_async_in_thread, parse_wikidata_company, company_name),
			return_exceptions=True,
		)
		if isinstance(domain_result, Exception):
			notes.append(f"Domain discovery failed: {domain_result}")
		else:
			try:
				resolved_domain, _ = domain_result
			except Exception as exc:
				notes.append(f"Domain discovery parse failed: {exc}")

		if isinstance(wikidata_result, Exception):
			notes.append(f"Wikidata lookup failed: {wikidata_result}")
		else:
			wikidata = wikidata_result if isinstance(wikidata_result, dict) else {}

		if not resolved_domain and wikidata.get("website"):
			resolved_domain = str(wikidata.get("website"))
			notes.append("Used Wikidata website as resolved domain fallback")

		merge_into(data, wikidata, field_sources, "wikidata", skip_if_present=set())
		if wikidata.get("wikidata_url"):
			sources.append(str(wikidata.get("wikidata_url")))
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

	merge_into(
		data,
		enrichment_data,
		field_sources,
		enrich_sources or "enrichment",
		skip_if_present=WIKIDATA_PRIORITY_FIELDS,
	)


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
) -> tuple[dict[str, Any], dict[str, str], dict[str, Any], str]:
	enrichment_data: dict[str, Any] = {}
	enrich_sources: dict[str, str] = {}
	scraper_dict: dict[str, Any] = {}
	aftermarket_data: dict[str, Any] = {}
	about_text = ""

	try:
		enrich_result, scraper_result, news_result, aftermarket_result = await asyncio.gather(
			asyncio.to_thread(enrich_company, company_name, resolved_domain, wikidata),
			asyncio.to_thread(get_about_page_text, resolved_domain or "", str(wikidata.get("website") or "")),
			asyncio.to_thread(find_recent_news, company_name, resolved_domain, str(wikidata.get("website") or "")),
			asyncio.to_thread(detect_aftermarket, resolved_domain or "", str(wikidata.get("website") or "")),
			return_exceptions=True,
		)
		enrichment_data, enrich_sources = _unpack_enrichment_result(enrich_result, notes)
		scraper_dict, scraper_label, about_text = _unpack_scraper_result(scraper_result, notes)
		news_items = _unpack_news_result(news_result, notes)
		if isinstance(aftermarket_result, Exception):
			notes.append(f"Aftermarket detection failed: {aftermarket_result}")
		elif isinstance(aftermarket_result, dict):
			aftermarket_data = aftermarket_result

		_merge_enrichment_fields(data, field_sources, enrichment_data, enrich_sources)
		merge_into(data, scraper_dict, field_sources, scraper_label, skip_if_present=set())
		merge_into(data, aftermarket_data, field_sources, "aftermarket_detector", skip_if_present=set())
		if scraper_dict.get("source_url"):
			sources.append(str(scraper_dict.get("source_url")))
		for aftermarket_key in ("parts_page", "service_page", "support_page", "customer_portal_page"):
			if isinstance(aftermarket_data.get(aftermarket_key), str) and aftermarket_data.get(aftermarket_key):
				sources.append(str(aftermarket_data.get(aftermarket_key)))
		if news_items:
			data["recent_news"] = news_items
			field_sources["recent_news"] = "news_service"
	except Exception as exc:
		notes.append(f"Parallel service step failed: {exc}")

	return (enrichment_data, enrich_sources, scraper_dict, about_text)


async def _step3_sequential(
	company_name: str,
	enrichment_data: dict[str, Any],
	about_text: str,
	data: dict[str, Any],
	field_sources: dict[str, str],
) -> None:
	try:
		if _is_empty(data.get("what_they_make")) and about_text:
			try:
				wtm = await asyncio.to_thread(extract_what_they_make, about_text)
				if not _is_empty(wtm):
					data["what_they_make"] = wtm
					field_sources["what_they_make"] = "scraper_regex"
			except Exception:
				pass
		if _is_empty(data.get("personalized_opening_line")):
			opening_line = _build_opening_line(company_name, data)
			if opening_line:
				data["personalized_opening_line"] = opening_line
				field_sources["personalized_opening_line"] = "opening_line_generator"
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

		for news_item in data.get("recent_news", []) if isinstance(data.get("recent_news", []), list) else []:
			if isinstance(news_item, dict):
				_append_if_url(news_item.get("url"))

		for value in (enrich_sources or {}).values():
			if isinstance(value, str) and value.startswith("http"):
				sources.append(value)

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
) -> ResearchResponse:
	total_started_at = time.perf_counter()
	notes: list[str] = []
	sources: list[str] = []
	data: dict[str, Any] = {}
	field_sources: dict[str, str] = {}

	stage_started_at = time.perf_counter()
	resolved_domain, wikidata = await _step1_discovery(company_name, extra_context, notes, sources, data, field_sources)
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
	)
	_log_timing(company_name, "step2_parallel_services", stage_started_at)

	stage_started_at = time.perf_counter()
	await _step3_sequential(
		company_name,
		enrichment_data,
		about_text,
		data,
		field_sources,
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

	return ResearchResponse(
		company_name=company_name,
		resolved_domain=resolved_domain,
		data=data,
		field_sources=field_sources,
		sources=sources,
		notes=notes,
	)
