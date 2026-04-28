from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

from app.config import HUNTER_API_KEYS, REQUEST_TIMEOUT, SESSION

logger = logging.getLogger(__name__)

AFTERMARKET_EMAIL_TOKENS = (
	"aftermarket",
	"after-market",
	"aftermarketservice",
	"parts",
	"spareparts",
	"spares",
	"service",
	"support",
)

NEGATIVE_TITLE_TOKENS = (
	"servicenow",
	"it ",
	"information technology",
	"software",
	"developer",
	"engineer",
	"marketing",
	"finance",
	"accounting",
	"hr",
	"human resources",
	"recruit",
	"recruiting",
	"talent",
	"people operations",
)

PREFERRED_TITLE_KEYWORDS = (
	"aftermarket",
	"after-market",
	"after market",
	"after sales",
	"after-sales",
	"service director",
	"service manager",
	"field service",
	"technical service",
	"parts",
	"spare parts",
	"customer support",
	"customer service",
	"business development",
	"commercial",
	"sales",
)

PREFERRED_SENIORITY = {"executive", "director", "vp", "head", "manager"}


def extract_domain(value: str) -> str:
	try:
		parsed = urlparse(value if "://" in value else f"https://{value}")
		host = (parsed.netloc or parsed.path).split(":")[0].lower().strip()
		return re.sub(r"^www\.", "", host)
	except Exception:
		return str(value or "").lower().strip()


def hunter_domain_candidates(domain: str) -> list[str]:
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


def _normalize_linkedin(value: Any, company: bool = False) -> str | None:
	if isinstance(value, dict):
		handle = _normalize_text(value.get("handle") or value.get("url") or value.get("linkedin"))
		if not handle:
			return None
		value = handle
	linkedin = _normalize_text(value)
	if not linkedin:
		return None
	if linkedin.startswith("http://") or linkedin.startswith("https://"):
		return linkedin
	if linkedin.startswith("linkedin.com/"):
		return f"https://{linkedin}"
	if company:
		return f"https://linkedin.com/{linkedin.lstrip('/')}"
	return f"https://linkedin.com/in/{linkedin.lstrip('/')}"


def _normalize_int_like(value: Any) -> str | None:
	if value is None:
		return None
	digits = re.sub(r"\D", "", str(value))
	return digits or None


def _parse_shorthand_number(token: str) -> int | None:
	text = str(token or "").strip().lower().replace(",", "")
	match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([kmb]?)", text)
	if not match:
		return None
	number = float(match.group(1))
	suffix = match.group(2)
	multipliers = {"": 1, "k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
	return int(number * multipliers.get(suffix, 1))


def normalize_employee_count(value: Any) -> str | None:
	if value is None:
		return None
	text = str(value).strip()
	range_match = re.search(r"(\d+(?:\.\d+)?\s*[kmb]?)\s*-\s*(\d+(?:\.\d+)?\s*[kmb]?)", text, flags=re.IGNORECASE)
	if range_match:
		upper = _parse_shorthand_number(range_match.group(2))
		if upper:
			return str(upper)
	return _normalize_int_like(text)


def _normalize_tags(value: Any) -> list[str]:
	if isinstance(value, list):
		return [item for item in (_normalize_text(item) for item in value) if item]
	text = _normalize_text(value)
	if not text:
		return []
	return [item.strip() for item in text.split(",") if item.strip()]


def _normalize_site_emails(value: Any) -> list[str]:
	items = value if isinstance(value, list) else []
	result: list[str] = []
	for item in items:
		if isinstance(item, str):
			email = item.strip().lower()
		elif isinstance(item, dict):
			email = str(item.get("value") or item.get("email") or "").strip().lower()
		else:
			email = ""
		if email and email not in result:
			result.append(email)
	return result


def collect_aftermarket_site_emails(site_emails: list[str]) -> list[str]:
	result: list[str] = []
	for email in site_emails:
		local_part = email.split("@", 1)[0].replace(".", "").replace("-", "")
		if any(token.replace("-", "") in local_part for token in AFTERMARKET_EMAIL_TOKENS):
			result.append(email)
	return result


def _normalize_country(profile: dict[str, Any]) -> str | None:
	for key in ("country", "hq_country", "country_name"):
		value = _normalize_text(profile.get(key))
		if value:
			return value
	geo = profile.get("geo")
	if isinstance(geo, dict):
		value = _normalize_text(geo.get("country"))
		if value:
			return value
	location = profile.get("location")
	if isinstance(location, dict):
		for key in ("country", "name"):
			value = _normalize_text(location.get(key))
			if value:
				return value
	return None


def _normalize_city(profile: dict[str, Any]) -> str | None:
	for key in ("city", "hq_city"):
		value = _normalize_text(profile.get(key))
		if value:
			return value
	geo = profile.get("geo")
	if isinstance(geo, dict):
		value = _normalize_text(geo.get("city"))
		if value:
			return value
	location = profile.get("location")
	if isinstance(location, dict):
		for key in ("city", "name"):
			value = _normalize_text(location.get(key))
			if value:
				return value
	return None


def _response_data_from_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
	last_error: Exception | None = None
	for index, api_key in enumerate(HUNTER_API_KEYS, start=1):
		request_params = dict(params)
		request_params["api_key"] = api_key
		try:
			response = SESSION.get(f"https://api.hunter.io/v2/{path}", params=request_params, timeout=REQUEST_TIMEOUT)
			response.raise_for_status()
			payload = response.json()
			return payload.get("data", {}) if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else {}
		except Exception as exc:
			last_error = exc
			status_code = getattr(getattr(exc, "response", None), "status_code", None)
			if status_code in {401, 403, 429}:
				logger.warning("Hunter key %s/%s exhausted or unauthorized for endpoint %s", index, len(HUNTER_API_KEYS), path)
				continue
			raise

	if last_error is not None:
		raise last_error
	return {}


def get_company_profile(domain: str) -> dict[str, Any]:
	if not HUNTER_API_KEYS:
		return {}

	for candidate_domain in hunter_domain_candidates(domain):
		for path in ("companies/find", "companies/enrich"):
			try:
				profile = _response_data_from_get(path, {"domain": candidate_domain})
				if not profile:
					continue

				site_emails = _normalize_site_emails(profile.get("emails") or profile.get("site_emails"))
				site = profile.get("site")
				if isinstance(site, dict) and not site_emails:
					site_emails = _normalize_site_emails(site.get("emailAddresses"))
				aftermarket_site_emails = collect_aftermarket_site_emails(site_emails)
				category = profile.get("category")
				category_dict = category if isinstance(category, dict) else {}
				metrics = profile.get("metrics")
				metrics_dict = metrics if isinstance(metrics, dict) else {}
				site_phone = None
				if isinstance(site, dict):
					phone_numbers = site.get("phoneNumbers")
					if isinstance(phone_numbers, list) and phone_numbers:
						site_phone = _normalize_text(phone_numbers[0])
				industry = (
					_normalize_text(profile.get("industry"))
					or _normalize_text(profile.get("sub_industry"))
					or _normalize_text(category_dict.get("industry"))
					or _normalize_text(category_dict.get("subIndustry"))
					or _normalize_text(category_dict.get("industryGroup"))
					or _normalize_text(profile.get("sector"))
					or _normalize_text(category_dict.get("sector"))
				)
				description = _normalize_text(profile.get("description"))
				company_profile = {
					"official_name": _normalize_text(profile.get("legal_name"))
					or _normalize_text(profile.get("legalName"))
					or _normalize_text(profile.get("name")),
					"description": description,
					"founded_year": _normalize_text(profile.get("founded") or profile.get("founded_year") or profile.get("foundedYear")),
					"hq_city": _normalize_city(profile),
					"hq_country": _normalize_country(profile),
					"industry": industry,
					"employee_count": normalize_employee_count(
						profile.get("employees")
						or profile.get("size")
						or metrics_dict.get("employees")
					),
					"employee_count_display": _normalize_text(
						profile.get("employees")
						or profile.get("size")
						or metrics_dict.get("employees")
					),
					"revenue": _normalize_text(
						profile.get("revenue")
						or metrics_dict.get("annualRevenue")
						or metrics_dict.get("estimatedAnnualRevenue")
					),
					"company_linkedin_url": _normalize_linkedin(profile.get("linkedin") or profile.get("linkedin_url"), company=True),
					"company_phone": _normalize_text(profile.get("phone")) or site_phone,
					"company_tags": _normalize_tags(profile.get("tags")),
					"site_emails": site_emails,
					"aftermarket_site_emails": aftermarket_site_emails,
					"hunter_domain": _normalize_text(profile.get("domain")) or candidate_domain,
				}
				if aftermarket_site_emails:
					company_profile["aftermarket_footprint"] = True
					company_profile["aftermarket_reason"] = "Hunter found service or parts-related email addresses on the company site."
				return {key: value for key, value in company_profile.items() if value not in (None, "", [], {})}
			except Exception as exc:
				logger.warning("Hunter company profile lookup failed for %s via %s: %s", candidate_domain, path, exc)
				continue
	return {}


def _is_likely_person_name(value: Any) -> bool:
	text = _normalize_text(value)
	if not text or len(text.split()) < 2:
		return False
	if any(token in text.lower() for token in ("team", "leadership", "management", "company", "about")):
		return False
	return bool(re.match(r"^[A-Z][A-Za-z\-\.'`]+(?:\s+[A-Z][A-Za-z\-\.'`]+){1,4}$", text))


def score_person(person: dict[str, Any]) -> int:
	title = str(person.get("position") or "").strip().lower()
	seniority = str(person.get("seniority") or "").strip().lower()
	score = 0

	if any(token in title for token in NEGATIVE_TITLE_TOKENS):
		score -= 8

	for keyword in PREFERRED_TITLE_KEYWORDS:
		if keyword in title:
			score += 8 if keyword in {"aftermarket", "after-market", "after market", "after sales", "after-sales"} else 5
			break

	if seniority in PREFERRED_SENIORITY:
		score += 3
	if "director" in title or title.startswith("vp") or "vice president" in title or title.startswith("head "):
		score += 2
	if person.get("linkedin"):
		score += 1
	if person.get("confidence"):
		try:
			score += min(int(person.get("confidence") or 0) // 20, 4)
		except Exception:
			pass
	return score


def get_people(domain: str) -> dict[str, Any]:
	if not HUNTER_API_KEYS:
		return {}

	for candidate_domain in hunter_domain_candidates(domain):
		for index, api_key in enumerate(HUNTER_API_KEYS, start=1):
			try:
				data = _response_data_from_get(
					"domain-search",
					{
						"domain": candidate_domain,
						"seniority": "director,executive,vp,head,manager",
						"api_key": api_key,
					},
				)
				emails = data.get("emails", []) if isinstance(data.get("emails"), list) else []
				people = [item for item in emails if isinstance(item, dict)]
				return {
					"domain": candidate_domain,
					"email_pattern": _normalize_text(data.get("pattern")),
					"people": people,
				}
			except Exception as exc:
				status_code = getattr(getattr(exc, "response", None), "status_code", None)
				if status_code in {401, 403, 429}:
					logger.warning("Hunter key %s/%s exhausted or unauthorized for people endpoint", index, len(HUNTER_API_KEYS))
					continue
				logger.warning("Hunter people lookup failed for %s: %s", candidate_domain, exc)
				continue
	return {}


def pick_best_contact(people_payload: dict[str, Any]) -> dict[str, Any] | None:
	people = people_payload.get("people", []) if isinstance(people_payload, dict) else []
	if not isinstance(people, list) or not people:
		return None

	scored = sorted(
		[item for item in people if isinstance(item, dict)],
		key=score_person,
		reverse=True,
	)
	for best in scored:
		name = _normalize_text(f"{best.get('first_name', '')} {best.get('last_name', '')}")
		title = _normalize_text(best.get("position") or best.get("seniority"))
		if not _is_likely_person_name(name) or not title or score_person(best) <= 0:
			continue
		return {
			"name": name,
			"title": title,
			"linkedin_url": _normalize_linkedin(best.get("linkedin")),
			"email": _normalize_text(best.get("value")),
			"source": "hunter",
			"confidence": _normalize_int_like(best.get("confidence")),
		}
	return None
