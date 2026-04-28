from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable

from app.llms import HAS_LLM, build_default_json_llm
from app.prompts import build_people_title_prompt
from app.services.hunter import extract_domain, get_people, normalize_employee_count, pick_best_contact

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


def _normalize_text(value: Any) -> str | None:
	if value is None:
		return None
	text = re.sub(r"\s+", " ", str(value)).strip()
	return text or None


def _normalize_linkedin(value: Any) -> str | None:
	linkedin = _normalize_text(value)
	if not linkedin:
		return None
	if linkedin.startswith("http://") or linkedin.startswith("https://"):
		return linkedin
	if linkedin.startswith("linkedin.com/"):
		return f"https://{linkedin}"
	return f"https://linkedin.com/in/{linkedin.lstrip('/')}"


def suggest_title_from_context(aftermarket_data: dict[str, Any], enrichment_data: dict[str, Any]) -> dict[str, str]:
	employee_count = 0
	try:
		employee_count = int(normalize_employee_count(enrichment_data.get("employee_count")) or "0")
	except Exception:
		employee_count = 0

	if aftermarket_data.get("aftermarket_footprint"):
		if aftermarket_data.get("service_page") and employee_count > 500:
			return {
				"suggested_title": "VP of Aftermarket Services",
				"reasoning": "Dedicated service presence plus larger headcount points to a VP-level service owner.",
			}
		if aftermarket_data.get("parts_page"):
			return {
				"suggested_title": "Director of Parts & Service",
				"reasoning": "Visible parts presence suggests a parts and service leader owns the motion.",
			}
		return {
			"suggested_title": "Director of After-Sales Services",
			"reasoning": "The company shows aftermarket signals on its website.",
		}

	if employee_count > 5000:
		return {
			"suggested_title": "VP of Sales & Commercial Operations",
			"reasoning": "In larger enterprises, ownership is often centralized at VP commercial level.",
		}
	if employee_count > 500:
		return {
			"suggested_title": "Commercial Director",
			"reasoning": "For mid-size firms, commercial leadership commonly spans service and sales decisions.",
		}
	return {
		"suggested_title": "General Manager / Sales Director",
		"reasoning": "At smaller firms, broad commercial ownership usually sits with GM or sales leadership.",
	}


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


def _invoke_title_llm(prompt: str) -> dict[str, Any]:
	if not HAS_LLM:
		return {}
	try:
		llm = build_default_json_llm(temperature=0)
		if llm is None:
			return {}
		response = llm.invoke(prompt)
		return _extract_json_dict(getattr(response, "content", ""))
	except Exception as exc:
		logger.warning("Title suggestion LLM failed: %s", exc)
	return {}


def suggest_title_with_llm(
	company_name: str,
	resolved_domain: str,
	aftermarket_data: dict[str, Any],
	enrichment_data: dict[str, Any],
) -> dict[str, str]:
	prompt = build_people_title_prompt(company_name, resolved_domain, aftermarket_data, enrichment_data)
	result = _invoke_title_llm(prompt)
	title = _normalize_text(result.get("suggested_title")) if isinstance(result, dict) else None
	reasoning = _normalize_text(result.get("reasoning")) if isinstance(result, dict) else None
	if title:
		return {
			"suggested_title": title,
			"reasoning": reasoning or "Suggested by LLM from company context.",
			"source": "llm_title_suggestion",
		}
	fallback = suggest_title_from_context(aftermarket_data, enrichment_data)
	return {
		**fallback,
		"source": "heuristic_title_fallback",
	}


def find_key_person(
	company_name: str,
	resolved_domain: str,
	aftermarket_data: dict[str, Any],
	enrichment_data: dict[str, Any],
	progress_cb: ProgressCallback | None = None,
) -> dict[str, Any]:
	result = {
		"name": None,
		"title": None,
		"linkedin_url": None,
		"email": None,
		"confidence": None,
		"source": "none",
		"suggested_title": None,
		"suggested_title_reasoning": None,
	}

	try:
		_emit_progress(progress_cb, "people.hunter", "info", f"Fetching Hunter contacts for {extract_domain(resolved_domain)}")
		hunter_people = get_people(resolved_domain)
		hunter_person = pick_best_contact(hunter_people)
		if hunter_person:
			result.update(
				{
					"name": hunter_person.get("name"),
					"title": hunter_person.get("title"),
					"linkedin_url": _normalize_linkedin(hunter_person.get("linkedin_url")),
					"email": _normalize_text(hunter_person.get("email")),
					"source": hunter_person.get("source") or "hunter",
					"confidence": hunter_person.get("confidence"),
				}
			)
			_emit_progress(progress_cb, "people.hunter", "completed", f"Selected Hunter contact: {result.get('title') or result.get('name')}")
			return result

		_emit_progress(progress_cb, "people.hunter", "fallback", "Hunter did not return a strong named contact, falling back to title suggestion")
		title_suggestion = suggest_title_with_llm(
			company_name=company_name,
			resolved_domain=extract_domain(resolved_domain),
			aftermarket_data=aftermarket_data,
			enrichment_data=enrichment_data,
		)
		result["source"] = title_suggestion.get("source") or "heuristic_title_fallback"
		result["suggested_title"] = title_suggestion.get("suggested_title")
		result["suggested_title_reasoning"] = title_suggestion.get("reasoning")
		result["title"] = title_suggestion.get("suggested_title")
		_emit_progress(progress_cb, "people.title", "completed", f"Selected fallback title: {result.get('title') or 'unknown'}")
		return result
	except Exception as exc:
		logger.warning("find_key_person failed for %s: %s", company_name, exc)
		title_suggestion = suggest_title_from_context(aftermarket_data, enrichment_data)
		result["source"] = "heuristic_title_fallback"
		result["suggested_title"] = title_suggestion.get("suggested_title")
		result["suggested_title_reasoning"] = title_suggestion.get("reasoning")
		result["title"] = title_suggestion.get("suggested_title")
		return result
