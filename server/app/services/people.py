from __future__ import annotations

import json
import logging
import os
import re
from typing import Any
from urllib.parse import urlparse

from app.config import GEMINI_API_KEY, GROQ_API_KEY, HUNTER_API_KEY, REQUEST_TIMEOUT, SESSION

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

PREFERRED_TITLE_KEYWORDS = (
	"aftermarket",
	"after-market",
	"after market",
	"service",
	"spare parts",
	"parts",
	"sales",
	"commercial",
	"business development",
	"customer success",
	"field service",
)

PREFERRED_SENIORITY = {"executive", "director", "vp"}

try:
	from langchain_google_genai import ChatGoogleGenerativeAI
	from langchain_groq import ChatGroq  # type: ignore[import-not-found]

	HAS_LLM = True
except Exception:
	ChatGoogleGenerativeAI = ChatGroq = None  # type: ignore[assignment]
	HAS_LLM = False


def extract_domain(value: str) -> str:
	try:
		parsed = urlparse(value if "://" in value else f"https://{value}")
		host = (parsed.netloc or parsed.path).split(":")[0].lower().strip()
		return re.sub(r"^www\.", "", host)
	except Exception:
		return str(value or "").lower().strip()


def _hunter_domain_candidates(domain: str) -> list[str]:
	clean_domain = extract_domain(domain)
	if not clean_domain:
		return []

	parts = [part for part in clean_domain.split(".") if part]
	candidates: list[str] = []
	last_start = max(0, len(parts) - 2)
	for index in range(0, last_start + 1):
		candidate = ".".join(parts[index:])
		if candidate and candidate not in candidates:
			candidates.append(candidate)
	return candidates


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


def _is_likely_person_name(value: Any) -> bool:
	text = _normalize_text(value)
	if not text or len(text.split()) < 2:
		return False
	if any(token in text.lower() for token in ("team", "leadership", "management", "company", "about")):
		return False
	return bool(re.match(r"^[A-Z][A-Za-z\-\.'`]+(?:\s+[A-Z][A-Za-z\-\.'`]+){1,4}$", text))


def _score_hunter_person(person: dict[str, Any]) -> int:
	title = str(person.get("position") or "").lower()
	seniority = str(person.get("seniority") or "").lower()
	score = 0
	if seniority in PREFERRED_SENIORITY:
		score += 3
	for keyword in PREFERRED_TITLE_KEYWORDS:
		if keyword in title:
			score += 5
			break
	if person.get("linkedin"):
		score += 1
	if person.get("confidence"):
		try:
			score += min(int(person.get("confidence") or 0) // 20, 4)
		except Exception:
			pass
	return score


def search_hunter(domain: str) -> dict[str, Any] | None:
	domain_candidates = _hunter_domain_candidates(domain)
	if not domain_candidates or not HUNTER_API_KEY:
		return None

	for candidate_domain in domain_candidates:
		try:
			response = SESSION.get(
				"https://api.hunter.io/v2/domain-search",
				params={
					"domain": candidate_domain,
					"seniority": "director,executive,vp",
					"api_key": HUNTER_API_KEY,
				},
				timeout=REQUEST_TIMEOUT,
			)
			response.raise_for_status()
			payload = response.json()
			data = payload.get("data", {}) if isinstance(payload, dict) else {}
			emails = data.get("emails", []) if isinstance(data, dict) else []
			if not isinstance(emails, list) or not emails:
				continue

			scored = sorted(
				[item for item in emails if isinstance(item, dict)],
				key=_score_hunter_person,
				reverse=True,
			)
			if not scored:
				continue

			best = scored[0]
			name = _normalize_text(f"{best.get('first_name', '')} {best.get('last_name', '')}")
			title = _normalize_text(best.get("position") or best.get("seniority"))
			if not _is_likely_person_name(name) or not title:
				continue

			return {
				"name": name,
				"title": title,
				"linkedin_url": _normalize_linkedin(best.get("linkedin")),
				"email": _normalize_text(best.get("value")),
				"source": "hunter",
			}
		except Exception as exc:
			logger.warning("Hunter lookup failed for %s: %s", candidate_domain, exc)
			continue

	return None


def suggest_title_from_context(aftermarket_data: dict[str, Any], enrichment_data: dict[str, Any]) -> dict[str, str]:
	employee_count = 0
	try:
		employee_count = int(re.sub(r"\D", "", str(enrichment_data.get("employee_count") or "")) or "0")
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


def _build_title_prompt(company_name: str, resolved_domain: str, aftermarket_data: dict[str, Any], enrichment_data: dict[str, Any]) -> str:
	return (
		"You are selecting the best target job title for a B2B trade-show outreach workflow.\n"
		"Choose the single most relevant role to approach when a real person's name could not be found.\n"
		"Prefer roles in aftermarket, service, parts, sales, commercial, or business development.\n"
		"Return JSON only with exactly these fields: suggested_title, reasoning.\n"
		"If aftermarket/service signals are present, bias toward those functions over generic sales roles.\n\n"
		f"Company: {company_name}\n"
		f"Domain: {resolved_domain}\n"
		f"Aftermarket data: {json.dumps(aftermarket_data, ensure_ascii=True)}\n"
		f"Enrichment data: {json.dumps(enrichment_data, ensure_ascii=True)}\n"
	)


def _invoke_title_llm(prompt: str) -> dict[str, Any]:
	if not HAS_LLM:
		return {}
	try:
		if GEMINI_API_KEY:
			llm = ChatGoogleGenerativeAI(
				model=GEMINI_MODEL,
				google_api_key=GEMINI_API_KEY,
				temperature=0,
				response_mime_type="application/json",
			)
			response = llm.invoke(prompt)
			return _extract_json_dict(getattr(response, "content", ""))
		if GROQ_API_KEY:
			llm = ChatGroq(model=GROQ_MODEL, groq_api_key=GROQ_API_KEY, temperature=0)
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
	prompt = _build_title_prompt(company_name, resolved_domain, aftermarket_data, enrichment_data)
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
) -> dict[str, Any]:
	result = {
		"name": None,
		"title": None,
		"linkedin_url": None,
		"email": None,
		"source": "none",
		"suggested_title": None,
		"suggested_title_reasoning": None,
	}

	try:
		hunter_person = search_hunter(resolved_domain)
		if hunter_person:
			result.update(hunter_person)
			return result

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
		return result
	except Exception as exc:
		logger.warning("find_key_person failed for %s: %s", company_name, exc)
		title_suggestion = suggest_title_from_context(aftermarket_data, enrichment_data)
		result["source"] = "heuristic_title_fallback"
		result["suggested_title"] = title_suggestion.get("suggested_title")
		result["suggested_title_reasoning"] = title_suggestion.get("reasoning")
		result["title"] = title_suggestion.get("suggested_title")
		return result
