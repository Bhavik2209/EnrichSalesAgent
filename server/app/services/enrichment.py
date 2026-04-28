from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable

from app.config import (
	CUFINDER_API_KEY,
	CUFINDER_API_KEYS,
	GEMINI_API_KEY,
	GROQ_API_KEY,
	REQUEST_TIMEOUT,
	SESSION,
	TECHNOLOGY_CHECKER_API_KEY,
)
from app.llms import HAS_LLM, build_default_llm, invoke_llm_with_retry
from app.prompts import ENRICHMENT_SYSTEM_PROMPT
from app.services.hunter import get_company_profile

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[str, str, str, dict[str, Any] | None], None]


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

STABLE_FIELDS = [
	"official_name",
	"founded_year",
	"hq_city",
	"hq_country",
	"industry",
	"parent_company",
	"description",
]

REFRESH_FIELDS = ["employee_count", "revenue"]

AUXILIARY_FIELDS = [
	"employee_count_display",
	"company_linkedin_url",
	"company_phone",
	"company_tags",
	"site_emails",
	"aftermarket_site_emails",
	"aftermarket_footprint",
	"aftermarket_reason",
]

ALL_ENRICH_FIELDS = STABLE_FIELDS + REFRESH_FIELDS + AUXILIARY_FIELDS

SOURCE_LABELS = {
	"get_hunter_company_profile": "hunter_company_profile",
	"enrich_from_technology_checker": "technology_checker",
	"enrich_from_cufinder": "cufinder_enc",
	"get_cufinder_revenue": "cufinder_car",
	"get_cufinder_employee_count": "cufinder_cec",
}

try:
	from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
	from langchain_core.tools import tool

	LANGCHAIN_AVAILABLE = HAS_LLM
except Exception:
	LANGCHAIN_AVAILABLE = False
	HumanMessage = SystemMessage = ToolMessage = None  # type: ignore[assignment]

	def tool(*_args: Any, **_kwargs: Any):
		def _decorator(func: Any) -> Any:
			return func

		return _decorator


def _is_missing(value: Any) -> bool:
	if value is None:
		return True
	if isinstance(value, str):
		return not value.strip()
	if isinstance(value, (list, dict, tuple, set)):
		return len(value) == 0
	return False


def _normalize_int_like(value: Any) -> str | None:
	if value is None:
		return None
	digits = re.sub(r"\D", "", str(value))
	return digits or None


def _employee_count_display_from_count(value: Any) -> str | None:
	count_text = _normalize_int_like(value)
	if not count_text:
		return None
	try:
		count = int(count_text)
	except Exception:
		return None

	if count <= 10:
		return "1-10"
	if count <= 50:
		return "11-50"
	if count <= 200:
		return "51-200"
	if count <= 500:
		return "201-500"
	if count <= 1000:
		return "501-1000"
	if count <= 5000:
		return "1001-5000"
	return "5000+"


def _can_fill_revenue(source: str) -> bool:
	return source == "cufinder_car"


def _normalize_text(value: Any) -> str | None:
	if value is None:
		return None
	text = re.sub(r"\s+", " ", str(value)).strip()
	return text or None


def _shorten_description(value: Any, max_sentences: int = 3, max_chars: int = 420) -> str | None:
	text = _normalize_text(value)
	if not text:
		return None

	sentences = re.split(r"(?<=[.!?])\s+", text)
	kept: list[str] = []
	for sentence in sentences:
		clean = sentence.strip()
		if not clean:
			continue
		kept.append(clean)
		if len(kept) >= max_sentences:
			break

	shortened = " ".join(kept).strip() if kept else text
	if len(shortened) > max_chars:
		shortened = shortened[:max_chars].rstrip(" ,;:-")
		if shortened and shortened[-1] not in ".!?":
			shortened += "."
	return shortened or None


def _normalize_lookup_domain(value: str | None) -> str:
	if not value:
		return ""
	domain = str(value).strip().lower()
	domain = re.sub(r"^https?://", "", domain)
	domain = domain.split("/")[0].split("?")[0].split("#")[0]
	domain = domain.split(":")[0]
	domain = re.sub(r"^www\.", "", domain)
	return domain.strip()


def _extract_parent_company_from_description(text: str | None) -> str | None:
	if not text:
		return None

	patterns = [
		r"(?:a\s+)?subsidiary of\s+([A-Z][A-Za-z0-9&.,'\-\s]{2,80})",
		r"wholly owned by\s+([A-Z][A-Za-z0-9&.,'\-\s]{2,80})",
		r"owned by\s+([A-Z][A-Za-z0-9&.,'\-\s]{2,80})",
		r"part of\s+([A-Z][A-Za-z0-9&.,'\-\s]{2,80})",
		r"division of\s+([A-Z][A-Za-z0-9&.,'\-\s]{2,80})",
		r"brand of\s+([A-Z][A-Za-z0-9&.,'\-\s]{2,80})",
	]
	for pattern in patterns:
		match = re.search(pattern, text, flags=re.IGNORECASE)
		if not match:
			continue
		candidate = re.sub(r"\s+", " ", match.group(1)).strip(" ,.")
		candidate = re.split(
			r"\b(?:with|that|which|and|for|since|founded|headquartered)\b",
			candidate,
			maxsplit=1,
			flags=re.IGNORECASE,
		)[0].strip(" ,.")
		if candidate and len(candidate) >= 3:
			return candidate
	return None


def _pick_first(payload: dict[str, Any], keys: list[str]) -> Any:
	for key in keys:
		if key in payload and not _is_missing(payload.get(key)):
			return payload.get(key)
	return None


def _normalize_employee_count_from_range(value: Any) -> str | None:
	if value is None:
		return None
	text = str(value).strip()
	range_match = re.search(r"(\d[\d,]*)\s*-\s*(\d[\d,]*)", text)
	if range_match:
		return re.sub(r"\D", "", range_match.group(2))
	return _normalize_int_like(text)


def _map_technology_checker_response(data: dict[str, Any]) -> dict[str, Any]:
	payload = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
	employee_count_value = payload.get("employees")
	if _is_missing(employee_count_value):
		employee_count_value = payload.get("associated_members")

	mapped: dict[str, Any] = {
		"employee_count": _normalize_employee_count_from_range(employee_count_value),
		"founded_year": _normalize_text(payload.get("founded")),
		"hq_city": _normalize_text(payload.get("city")),
		"hq_country": _normalize_text(payload.get("country")),
		"industry": _normalize_text(payload.get("industry")),
		"official_name": _normalize_text(payload.get("company_name")),
		"description": _shorten_description(payload.get("description"), max_sentences=3, max_chars=420),
		"parent_company": _normalize_text(payload.get("company_type")),
	}

	if _is_missing(mapped.get("parent_company")):
		mapped["parent_company"] = _extract_parent_company_from_description(mapped.get("description"))

	return {k: v for k, v in mapped.items() if not _is_missing(v)}


def _map_cufinder_enc_response(data: dict[str, Any]) -> dict[str, Any]:
	payload = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
	company = payload.get("company", {}) if isinstance(payload.get("company"), dict) else {}

	mapped: dict[str, Any] = {
		"employee_count": _normalize_int_like(company.get("employee_count")),
		"founded_year": _normalize_text(company.get("founded_year")),
		"hq_city": _normalize_text(company.get("city")),
		"hq_country": _normalize_text(company.get("country")),
		"industry": _normalize_text(company.get("industry")),
		"official_name": _normalize_text(company.get("name")),
		"description": _normalize_text(company.get("description")),
		"parent_company": _normalize_text(company.get("parent_company")),
	}
	if _is_missing(mapped.get("parent_company")):
		mapped["parent_company"] = _extract_parent_company_from_description(mapped.get("description"))
	return {k: v for k, v in mapped.items() if not _is_missing(v)}


def _is_cufinder_credit_error(payload: dict[str, Any]) -> bool:
	message_parts = [
		str(payload.get("message") or ""),
		str(payload.get("detail") or ""),
		str(payload.get("error") or ""),
	]
	data = payload.get("data")
	if isinstance(data, dict):
		message_parts.extend(
			[
				str(data.get("message") or ""),
				str(data.get("detail") or ""),
				str(data.get("error") or ""),
			]
		)

	message = " ".join(part.strip().lower() for part in message_parts if part and part.strip())
	if not message:
		return False

	return (
		"no credit" in message
		or "insufficient credit" in message
		or "out of credit" in message
		or "quota exceeded" in message
		or "usage limit" in message
	)


def _post_cufinder(endpoint: str, query: str) -> dict[str, Any]:
	last_error: Exception | None = None
	for index, api_key in enumerate(CUFINDER_API_KEYS, start=1):
		try:
			response = SESSION.post(
				endpoint,
				headers={
					"Content-Type": "application/x-www-form-urlencoded",
					"x-api-key": api_key,
				},
				data={"query": query},
				timeout=REQUEST_TIMEOUT,
			)
			response.raise_for_status()
			parsed = response.json()
			if not isinstance(parsed, dict):
				return {}
			if _is_cufinder_credit_error(parsed):
				logger.warning("CUFinder key %s/%s reported no credits for endpoint %s", index, len(CUFINDER_API_KEYS), endpoint)
				continue
			return parsed
		except Exception as exc:
			last_error = exc
			status_code = getattr(getattr(exc, "response", None), "status_code", None)
			if status_code in {401, 403, 429}:
				logger.warning("CUFinder key %s/%s exhausted or unauthorized for endpoint %s", index, len(CUFINDER_API_KEYS), endpoint)
				continue
			raise

	if last_error is not None:
		raise last_error
	raise RuntimeError("No CUFinder API keys configured")


@tool
def get_hunter_company_profile(domain: str) -> dict:
	"""Fetches company profile, site emails, and lightweight aftermarket clues from Hunter."""
	lookup_domain = _normalize_lookup_domain(domain)
	if not lookup_domain:
		return {}
	return get_company_profile(lookup_domain)


@tool
def enrich_from_technology_checker(domain: str) -> dict:
	"""Fetches company profile from Technology Checker. Use this first for any missing company fields."""
	lookup_domain = _normalize_lookup_domain(domain)
	if not lookup_domain or not TECHNOLOGY_CHECKER_API_KEY:
		return {}

	try:
		response = SESSION.get(
			f"https://api.technologychecker.io/v1/company/{lookup_domain}",
			headers={"Authorization": f"Bearer {TECHNOLOGY_CHECKER_API_KEY}"},
			timeout=REQUEST_TIMEOUT,
		)
		response.raise_for_status()
		parsed = response.json()
		if not isinstance(parsed, dict):
			return {}
		return _map_technology_checker_response(parsed)
	except Exception as exc:
		logger.warning("Technology Checker enrichment failed for %s: %s", lookup_domain, exc)
		return {}


@tool
def enrich_from_cufinder(company_name: str, domain: str) -> dict:
	"""Fetches company enrichment from CUFinder /enc endpoint. Use only if Technology Checker did not return the needed fields."""
	if not CUFINDER_API_KEYS:
		return {}

	endpoint = "https://api.cufinder.io/v2/enc"
	queries = [q for q in [domain, company_name] if q]
	for query in queries:
		try:
			parsed = _post_cufinder(endpoint, query)
			mapped = _map_cufinder_enc_response(parsed)
			if mapped:
				return mapped
		except Exception as exc:
			logger.warning("CUFinder /enc failed for %s: %s", query, exc)
			continue
	return {}


@tool
def get_cufinder_revenue(company_name: str, domain: str) -> str | None:
	"""Gets annual revenue from CUFinder /car endpoint. Use this specifically for revenue if other sources did not return it."""
	if not CUFINDER_API_KEYS:
		return None

	endpoint = "https://api.cufinder.io/v2/car"
	queries = [q for q in [domain, company_name] if q]
	for query in queries:
		try:
			parsed = _post_cufinder(endpoint, query)
			payload = parsed.get("data", {}) if isinstance(parsed.get("data"), dict) else {}
			revenue = _normalize_text(payload.get("annual_revenue") or payload.get("revenue"))
			if revenue:
				return revenue
		except Exception as exc:
			logger.warning("CUFinder /car failed for %s: %s", query, exc)
			continue
	return None


@tool
def get_cufinder_employee_count(company_name: str, domain: str) -> str | None:
	"""Gets employee headcount from CUFinder /cec endpoint broken down by country. Use for employee_count if other sources missed it."""
	if not CUFINDER_API_KEYS:
		return None

	endpoint = "https://api.cufinder.io/v2/cec"
	queries = [q for q in [domain, company_name] if q]
	for query in queries:
		try:
			parsed = _post_cufinder(endpoint, query)
			payload = parsed.get("data", {}) if isinstance(parsed.get("data"), dict) else {}
			countries = payload.get("countries", {}) if isinstance(payload.get("countries"), dict) else {}
			total = 0
			for _, count in countries.items():
				digits = _normalize_int_like(count)
				if digits:
					total += int(digits)
			if total > 1:
				return str(total)
			if total == 1:
				logger.warning("Ignoring suspicious CUFinder /cec employee count=1 for %s (%s)", company_name, domain)
		except Exception as exc:
			logger.warning("CUFinder /cec failed for %s: %s", query, exc)
			continue
	return None


def _extract_json_dict(text: Any) -> dict[str, Any]:
	if isinstance(text, dict):
		return text
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
		pass

	start = raw.find("{")
	end = raw.rfind("}")
	if start != -1 and end != -1 and end > start:
		try:
			parsed = json.loads(raw[start : end + 1])
			return parsed if isinstance(parsed, dict) else {}
		except Exception:
			return {}
	return {}


def build_enrichment_agent() -> dict[str, Any] | None:
	if not LANGCHAIN_AVAILABLE:
		logger.warning("LangChain dependencies are unavailable; enrichment agent will run with deterministic fallback")
		return None

	llm = None
	try:
		llm = build_default_llm(temperature=0)
	except Exception as exc:
		logger.warning("Failed to initialize LLM client: %s", exc)
		llm = None

	if llm is None:
		return None

	tools = [
		get_hunter_company_profile,
		enrich_from_technology_checker,
		enrich_from_cufinder,
		get_cufinder_revenue,
		get_cufinder_employee_count,
	]

	try:
		bound_llm = llm.bind_tools(tools)
	except Exception as exc:
		logger.warning("Failed to bind tools to LLM: %s", exc)
		return None

	return {
		"llm": bound_llm,
		"tools": {tool_obj.name: tool_obj for tool_obj in tools},
		"system_prompt": ENRICHMENT_SYSTEM_PROMPT,
	}


def _invoke_tool_safely(tool_name: str, tool_map: dict[str, Any], args: dict[str, Any]) -> Any:
	tool_obj = tool_map.get(tool_name)
	if tool_obj is None:
		return {}

	try:
		return tool_obj.invoke(args)
	except Exception as exc:
		logger.warning("Tool invocation failed for %s: %s", tool_name, exc)
		if tool_name in {"get_cufinder_revenue", "get_cufinder_employee_count"}:
			return None
		return {}


def _call_tool_direct(tool_obj: Any, args: dict[str, Any]) -> Any:
	try:
		if hasattr(tool_obj, "invoke"):
			return tool_obj.invoke(args)
		return tool_obj(**args)
	except Exception as exc:
		logger.warning("Direct tool call failed: %s", exc)
		return None


def _run_agent_tool_loop(
	agent: dict[str, Any],
	company_name: str,
	domain: str,
	already_known: dict[str, Any],
) -> tuple[list[tuple[str, Any]], dict[str, Any]]:
	if not LANGCHAIN_AVAILABLE:
		return ([], {})

	llm = agent["llm"]
	tools = agent["tools"]
	payload = {
		"company_name": company_name,
		"domain": domain,
		"already_known": already_known,
		"target_fields": ALL_ENRICH_FIELDS,
	}

	messages = [
		SystemMessage(content=agent["system_prompt"]),
		HumanMessage(content=json.dumps(payload, ensure_ascii=True)),
	]

	tool_events: list[tuple[str, Any]] = []
	final_model_data: dict[str, Any] = {}

	for _ in range(8):
		ai_message = invoke_llm_with_retry(llm, messages, label="enrichment agent")
		if ai_message is None:
			logger.warning("LLM invocation failed during tool loop")
			break

		tool_calls = getattr(ai_message, "tool_calls", None) or []
		if not tool_calls:
			final_model_data = _extract_json_dict(getattr(ai_message, "content", ""))
			break

		messages.append(ai_message)
		for tool_call in tool_calls:
			tool_name = tool_call.get("name", "")
			args = tool_call.get("args", {})
			if not isinstance(args, dict):
				args = {}
			result = _invoke_tool_safely(tool_name, tools, args)
			tool_events.append((tool_name, result))

			messages.append(
				ToolMessage(
					content=json.dumps(result, ensure_ascii=True, default=str),
					tool_call_id=tool_call.get("id", ""),
				)
			)

	return (tool_events, final_model_data)


def _run_required_refresh_tools(company_name: str, domain: str) -> list[tuple[str, Any]]:
	results: list[tuple[str, Any]] = []

	results.append(
		(
			"get_hunter_company_profile",
			_call_tool_direct(get_hunter_company_profile, {"domain": domain}) if domain else {},
		)
	)
	results.append(
		(
			"enrich_from_technology_checker",
			_call_tool_direct(enrich_from_technology_checker, {"domain": domain}) if domain else {},
		)
	)
	results.append(
		(
			"get_cufinder_revenue",
			_call_tool_direct(get_cufinder_revenue, {"company_name": company_name, "domain": domain}),
		)
	)
	results.append(
		(
			"get_cufinder_employee_count",
			_call_tool_direct(get_cufinder_employee_count, {"company_name": company_name, "domain": domain}),
		)
	)
	return results


def _seed_stable_from_wikidata(wikidata_data: dict[str, Any], merged: dict[str, Any], field_sources: dict[str, str]) -> None:
	for field_name in STABLE_FIELDS:
		value = wikidata_data.get(field_name)
		if _is_missing(value):
			continue
		merged[field_name] = value
		field_sources[field_name] = "wikidata"


def _apply_dict_tool_result(
	source: str,
	result: dict[str, Any],
	merged: dict[str, Any],
	field_sources: dict[str, str],
) -> None:
	for field_name, value in result.items():
		if field_name not in ALL_ENRICH_FIELDS or _is_missing(value):
			continue

		if source == "technology_checker" and field_name == "employee_count":
			merged[field_name] = value
			field_sources[field_name] = source
			display_value = _employee_count_display_from_count(value)
			if display_value:
				merged["employee_count_display"] = display_value
				field_sources["employee_count_display"] = source
			continue

		if source == "hunter_company_profile":
			merged[field_name] = value
			field_sources[field_name] = source
			if field_name == "employee_count":
				display_value = _employee_count_display_from_count(value)
				if display_value:
					merged["employee_count_display"] = display_value
					field_sources["employee_count_display"] = source
			continue

		if field_name in REFRESH_FIELDS:
			if field_name == "revenue" and not _can_fill_revenue(source):
				continue
			if field_name == "employee_count" and source == "cufinder_cec" and not _is_missing(merged.get(field_name)):
				continue
			if _is_missing(merged.get(field_name)):
				merged[field_name] = value
				field_sources[field_name] = source
			continue

		if _is_missing(merged.get(field_name)):
			merged[field_name] = value
			field_sources[field_name] = source


def _apply_scalar_tool_result(
	tool_name: str,
	source: str,
	result: Any,
	merged: dict[str, Any],
	field_sources: dict[str, str],
) -> None:
	if _is_missing(result):
		return

	if tool_name == "get_cufinder_revenue":
		merged["revenue"] = result
		field_sources["revenue"] = source
	elif tool_name == "get_cufinder_employee_count":
		if not _is_missing(merged.get("employee_count")):
			return
		merged["employee_count"] = result
		field_sources["employee_count"] = source
		display_value = _employee_count_display_from_count(result)
		if display_value:
			merged["employee_count_display"] = display_value
			field_sources["employee_count_display"] = source


def _soft_fill_from_model(model_data: dict[str, Any], merged: dict[str, Any], field_sources: dict[str, str]) -> None:
	for field_name in ALL_ENRICH_FIELDS:
		if field_name == "revenue":
			continue
		if not _is_missing(merged.get(field_name)):
			continue
		candidate = model_data.get(field_name)
		if _is_missing(candidate):
			continue
		merged[field_name] = candidate
		field_sources[field_name] = field_sources.get(field_name, "agent_final")


def _apply_refresh_fallbacks_from_wikidata(
	wikidata_data: dict[str, Any],
	merged: dict[str, Any],
	field_sources: dict[str, str],
) -> None:
	for field_name in REFRESH_FIELDS:
		if field_name == "revenue":
			continue
		if not _is_missing(merged.get(field_name)):
			continue
		wiki_value = wikidata_data.get(field_name)
		if _is_missing(wiki_value):
			continue
		merged[field_name] = wiki_value
		field_sources[field_name] = "wikidata_fallback"


def _merge_tool_events(
	tool_events: list[tuple[str, Any]],
	model_data: dict[str, Any],
	wikidata_data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
	merged: dict[str, Any] = {}
	field_sources: dict[str, str] = {}

	_seed_stable_from_wikidata(wikidata_data, merged, field_sources)

	for tool_name, result in tool_events:
		source = SOURCE_LABELS.get(tool_name, tool_name)
		if result is None:
			continue

		if isinstance(result, dict):
			_apply_dict_tool_result(source, result, merged, field_sources)
			continue

		_apply_scalar_tool_result(tool_name, source, result, merged, field_sources)

	if not _is_missing(merged.get("employee_count")):
		display_value = _employee_count_display_from_count(merged.get("employee_count"))
		if display_value:
			merged["employee_count_display"] = display_value
			field_sources["employee_count_display"] = field_sources.get("employee_count", field_sources.get("employee_count_display", "derived_employee_count"))

	_soft_fill_from_model(model_data, merged, field_sources)
	_apply_refresh_fallbacks_from_wikidata(wikidata_data, merged, field_sources)

	return (merged, field_sources)


def enrich_company(
	company_name: str,
	resolved_domain: str | None,
	wikidata_data: dict[str, Any] | None,
	progress_cb: ProgressCallback | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
	wikidata_data = wikidata_data or {}

	already_known = {
		field_name: wikidata_data.get(field_name)
		for field_name in STABLE_FIELDS
		if not _is_missing(wikidata_data.get(field_name))
	}

	domain = (resolved_domain or wikidata_data.get("website") or "").strip()
	domain = _normalize_lookup_domain(domain)

	tool_events: list[tuple[str, Any]] = []
	model_data: dict[str, Any] = {}

	hunter_result = _call_tool_direct(get_hunter_company_profile, {"domain": domain}) if domain else {}
	tool_events.append(("get_hunter_company_profile", hunter_result or {}))
	if isinstance(hunter_result, dict) and hunter_result:
		emit_message = "Hunter returned company profile data"
		if hunter_result.get("description"):
			emit_message = "Hunter returned a usable company description"
		_emit_progress(progress_cb, "hunter.company", "completed", emit_message)
		if hunter_result.get("aftermarket_footprint") is True:
			_emit_progress(progress_cb, "hunter.aftermarket", "completed", "Hunter found positive aftermarket email evidence")
	else:
		_emit_progress(progress_cb, "hunter.company", "fallback", "Hunter company profile did not return usable company data")

	tech_result = _call_tool_direct(enrich_from_technology_checker, {"domain": domain}) if domain else {}
	tool_events.append(("enrich_from_technology_checker", tech_result or {}))
	if isinstance(tech_result, dict) and tech_result:
		_emit_progress(progress_cb, "technology_checker", "completed", "Technology Checker returned fallback company fields")

	missing_stable_fields = [
		field_name
		for field_name in STABLE_FIELDS
		if _is_missing(already_known.get(field_name))
		and _is_missing((hunter_result or {}).get(field_name) if isinstance(hunter_result, dict) else None)
		and _is_missing((tech_result or {}).get(field_name) if isinstance(tech_result, dict) else None)
	]
	if missing_stable_fields:
		_emit_progress(progress_cb, "cufinder.enrichment", "info", "Trying CUFinder company enrichment fallback")
		cufinder_result = _call_tool_direct(enrich_from_cufinder, {"company_name": company_name, "domain": domain}) or {}
		tool_events.append(("enrich_from_cufinder", cufinder_result))
		if isinstance(cufinder_result, dict) and cufinder_result:
			_emit_progress(progress_cb, "cufinder.enrichment", "completed", "CUFinder returned fallback company fields")

	_emit_progress(progress_cb, "revenue", "info", "Checking revenue sources")
	tool_events.append(
		(
			"get_cufinder_revenue",
			_call_tool_direct(get_cufinder_revenue, {"company_name": company_name, "domain": domain}),
		)
	)
	tool_events.append(
		(
			"get_cufinder_employee_count",
			_call_tool_direct(get_cufinder_employee_count, {"company_name": company_name, "domain": domain}),
		)
	)

	merged_data, field_sources = _merge_tool_events(
		tool_events=tool_events,
		model_data=model_data,
		wikidata_data=wikidata_data,
	)
	if merged_data.get("revenue"):
		revenue_source = field_sources.get("revenue") if isinstance(field_sources.get("revenue"), str) else "enrichment"
		_emit_progress(progress_cb, "revenue", "completed", f"Revenue available from {revenue_source}")
	else:
		_emit_progress(progress_cb, "revenue", "fallback", "Revenue was not found from the current providers")

	return (merged_data, field_sources)

