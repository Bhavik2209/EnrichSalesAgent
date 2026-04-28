from __future__ import annotations

import concurrent.futures
import logging
import re
from typing import Any
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from app.config import REQUEST_TIMEOUT, SESSION

logger = logging.getLogger(__name__)
SITEMAP_CANDIDATE_PATHS = (
	"/sitemap.xml",
	"/sitemap-index.xml",
	"/sitemap/sitemap.xml",
	"/sitemap/sitemap_index.xml",
)
MAX_SITEMAP_URLS = 8
MAX_SITEMAP_LINKS = 250
AFTERMARKET_PROBE_WORKERS = 6
COMMON_AFTERMARKET_PATHS = (
	"/parts",
	"/spare-parts",
	"/service",
	"/services",
	"/support",
	"/suppliers",
	"/supplier-portal",
	"/suppliers-portal",
	"/help",
	"/portal",
	"/customer-portal",
	"/dealer-portal",
	"/login",
	"/signin",
	"/my-account",
)
PRIMARY_AFTERMARKET_CATEGORIES = ("parts_page", "service_page", "support_page")


def extract_domain(url: str) -> str:
	try:
		parsed = urlparse(url if "://" in url else f"https://{url}")
		host = (parsed.netloc or parsed.path).split(":")[0].lower().strip()
		return re.sub(r"^www\.", "", host)
	except Exception:
		return str(url).lower().strip()


def _default_aftermarket() -> dict[str, Any]:
	return {
		"aftermarket_footprint": False,
		"parts_page": None,
		"service_page": None,
		"support_page": None,
		"customer_portal_page": None,
		"portal_detected": False,
		"aftermarket_reason": "Aftermarket detection failed or no data",
	}


def _clean_anchor_text(text: str) -> str:
	return re.sub(r"\s+", " ", str(text or "")).strip()[:80]


def _fetch_text(url: str) -> str:
	response = SESSION.get(url, timeout=REQUEST_TIMEOUT)
	response.raise_for_status()
	return response.text


def _candidate_domains(*values: str | None) -> list[str]:
	seen: list[str] = []
	for value in values:
		candidate = extract_domain(str(value or ""))
		if candidate and candidate not in seen:
			seen.append(candidate)
	return seen


AFTERMARKET_KEYWORDS = {
	"parts_page": ["parts", "spare parts", "replacement parts", "genuine parts", "parts and service"],
	"service_page": ["service", "services", "maintenance", "repair", "field service", "after sales"],
	"support_page": ["support", "technical support", "help", "customer support", "faq", "knowledge base"],
	"customer_portal_page": ["portal", "customer portal", "dealer portal", "supplier portal", "suppliers portal", "login", "sign in", "my account", "dealer login", "supplier login"],
}


def _sitemap_candidates_from_robots(clean_domain: str) -> list[str]:
	try:
		robots_text = _fetch_text(f"https://{clean_domain}/robots.txt")
	except Exception:
		return []

	candidates: list[str] = []
	for line in robots_text.splitlines():
		match = re.match(r"(?i)\s*sitemap:\s*(\S+)", line.strip())
		if not match:
			continue
		candidate = match.group(1).strip()
		if candidate and candidate not in candidates:
			candidates.append(candidate)
	return candidates


def _parse_sitemap_document(xml_text: str, clean_domain: str) -> tuple[list[str], list[str]]:
	root = ElementTree.fromstring(xml_text)
	tag_name = root.tag.lower()
	locs = [str(loc.text or "").strip() for loc in root.findall(".//{*}loc")]
	locs = [loc for loc in locs if loc]
	if "sitemapindex" in tag_name:
		nested = [loc for loc in locs if extract_domain(loc) == clean_domain]
		return (nested[:MAX_SITEMAP_URLS], [])
	links = [loc for loc in locs if extract_domain(loc) == clean_domain]
	return ([], links[:MAX_SITEMAP_LINKS])


def fetch_links_from_sitemap(domain: str) -> list[dict[str, str]]:
	clean_domain = extract_domain(domain)
	if not clean_domain:
		return []

	candidate_urls: list[str] = [f"https://{clean_domain}{path}" for path in SITEMAP_CANDIDATE_PATHS]
	for robots_candidate in _sitemap_candidates_from_robots(clean_domain):
		if robots_candidate not in candidate_urls:
			candidate_urls.append(robots_candidate)

	visited: set[str] = set()
	discovered_links: list[dict[str, str]] = []
	last_error: Exception | None = None
	tried_urls: list[str] = []

	while candidate_urls and len(visited) < MAX_SITEMAP_URLS and len(discovered_links) < MAX_SITEMAP_LINKS:
		candidate_url = candidate_urls.pop(0)
		if candidate_url in visited:
			continue
		visited.add(candidate_url)
		tried_urls.append(candidate_url)
		try:
			xml_text = _fetch_text(candidate_url)
			nested_sitemaps, links = _parse_sitemap_document(xml_text, clean_domain)
			for nested_url in nested_sitemaps:
				if nested_url not in visited and nested_url not in candidate_urls:
					candidate_urls.append(nested_url)
			for link_url in links:
				discovered_links.append({"url": link_url, "anchor_text": ""})
		except Exception as exc:
			last_error = exc

	if not discovered_links and last_error is not None:
		logger.warning(
			"Sitemap fetch failed for %s after trying %s: %s",
			domain,
			", ".join(tried_urls),
			last_error,
		)
	return discovered_links


def _fallback_homepage_links(domain: str) -> list[dict[str, str]]:
	clean_domain = extract_domain(domain)
	try:
		base = f"https://{clean_domain}"
		response = SESSION.get(base, timeout=REQUEST_TIMEOUT)
		response.raise_for_status()
		soup = BeautifulSoup(response.text, "html.parser")
		results: list[dict[str, str]] = []
		for anchor in soup.select("a[href]"):
			href = anchor.get("href", "").strip()
			if not href:
				continue
			absolute = urljoin(base, href)
			if extract_domain(absolute) != clean_domain:
				continue
			results.append({"url": absolute, "anchor_text": _clean_anchor_text(anchor.get_text(" ", strip=True))})
		return results
	except Exception as exc:
		logger.warning("BeautifulSoup homepage fallback failed for %s: %s", domain, exc)
		return []


def _probe_common_aftermarket_paths(domain: str) -> list[dict[str, str]]:
	clean_domain = extract_domain(domain)
	if not clean_domain:
		return []

	def _probe_one(path: str) -> dict[str, str] | None:
		url = f"https://{clean_domain}{path}"
		try:
			response = SESSION.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
			if response.status_code >= 400:
				return None
			final_url = str(getattr(response, "url", url) or url).strip()
			if extract_domain(final_url) != clean_domain:
				return None
			anchor = path.strip("/").replace("-", " ")
			return {"url": final_url, "anchor_text": anchor}
		except Exception:
			return None

	results: list[dict[str, str]] = []
	with concurrent.futures.ThreadPoolExecutor(max_workers=min(AFTERMARKET_PROBE_WORKERS, len(COMMON_AFTERMARKET_PATHS))) as executor:
		futures = [executor.submit(_probe_one, path) for path in COMMON_AFTERMARKET_PATHS]
		for future in concurrent.futures.as_completed(futures):
			try:
				result = future.result()
			except Exception:
				result = None
			if result:
				results.append(result)
	return results


def _score_bucket_aftermarket(url_l: str, anchor_l: str, keywords: list[str]) -> int:
	total = 0
	for kw in keywords:
		if kw in anchor_l:
			total += 3
		elif kw in url_l:
			total += 2
	return total


def _link_tie_breaker(anchor_l: str, url_l: str) -> tuple[int, int]:
	anchor_hits = int(any(anchor_l))
	short_url_bonus = max(0, 200 - len(url_l))
	return (anchor_hits, short_url_bonus)


def _score_single_aftermarket_link(link: dict[str, str], groups: dict[str, list[str]]) -> dict[str, Any] | None:
	url = str(link.get("url", "")).strip()
	anchor = str(link.get("anchor_text", "")).strip()
	if not url:
		return None

	url_l, anchor_l = url.lower(), anchor.lower()
	combined = f"{url_l} {anchor_l}"
	scores = dict.fromkeys(groups.keys(), 0)
	for key, keywords in groups.items():
		scores[key] = _score_bucket_aftermarket(url_l, anchor_l, keywords)

	if any(token in combined for token in ("portal", "login", "dealer", "supplier")):
		scores["customer_portal_page"] = int(scores["customer_portal_page"]) + 2

	if max((int(v) for v in scores.values()), default=0) <= 0:
		return None

	return {"url": url, "anchor_text": anchor, "scores": scores}


def fetch_links_from_homepage(domain: str) -> list[dict[str, str]]:
	return _fallback_homepage_links(domain)


def score_links_for_aftermarket(links: list[dict[str, str]]) -> list[dict[str, Any]]:
	try:
		scored = [_score_single_aftermarket_link(link, AFTERMARKET_KEYWORDS) for link in (links or [])]
		return [item for item in scored if item is not None]
	except Exception as exc:
		logger.warning("Aftermarket scoring failed: %s", exc)
		return []


def _dedupe_links(links: list[dict[str, str]]) -> list[dict[str, str]]:
	seen: dict[str, dict[str, str]] = {}
	for link in links:
		url = str(link.get("url", "")).strip()
		if not url:
			continue
		existing = seen.get(url)
		if existing is None or len(str(link.get("anchor_text", "")).strip()) > len(str(existing.get("anchor_text", "")).strip()):
			seen[url] = {"url": url, "anchor_text": str(link.get("anchor_text", "")).strip()}
	return list(seen.values())


def _pick_best_links(scored_links: list[dict[str, Any]]) -> dict[str, str | None]:
	result: dict[str, str | None] = {
		"parts_page": None,
		"service_page": None,
		"support_page": None,
		"customer_portal_page": None,
	}
	for category in result:
		best: tuple[int, tuple[int, int], str] | None = None
		best_url: str | None = None
		for item in scored_links:
			scores = item.get("scores", {})
			score = int(scores.get(category, 0)) if isinstance(scores, dict) else 0
			if score <= 0:
				continue
			anchor_l = str(item.get("anchor_text", "")).lower()
			url_l = str(item.get("url", "")).lower()
			candidate_rank = (score, _link_tie_breaker(anchor_l, url_l), url_l)
			if best is None or candidate_rank > best:
				best = candidate_rank
				best_url = str(item.get("url", "")).strip() or None
		result[category] = best_url
	return result


def _build_aftermarket_reason(result: dict[str, Any]) -> str:
	reasons: list[str] = []
	if result.get("parts_page"):
		reasons.append("Parts section found")
	if result.get("service_page"):
		reasons.append("Service section found")
	if result.get("support_page"):
		reasons.append("Support section found")
	if result.get("customer_portal_page"):
		reasons.append("Customer/dealer/supplier portal appears to exist")
	return " | ".join(reasons) if reasons else "No aftermarket links detected."


def _result_from_best_links(best_links: dict[str, str | None]) -> dict[str, Any]:
	portal_detected = bool(best_links.get("customer_portal_page"))
	aftermarket_footprint = any(best_links.values())
	return {
		"aftermarket_footprint": bool(aftermarket_footprint),
		"parts_page": best_links.get("parts_page"),
		"service_page": best_links.get("service_page"),
		"support_page": best_links.get("support_page"),
		"customer_portal_page": best_links.get("customer_portal_page"),
		"portal_detected": portal_detected,
		"aftermarket_reason": _build_aftermarket_reason(best_links),
	}


def _first_clue_result(best_links: dict[str, str | None]) -> dict[str, Any]:
	# First-clue mode: once we find a solid aftermarket signal, stop there.
	# We keep only the first strongest page and do not continue building a full map.
	for field_name, reason in (
		("parts_page", "Parts section found"),
		("service_page", "Service section found"),
		("support_page", "Support section found"),
		("customer_portal_page", "Customer/dealer/supplier portal appears to exist"),
	):
		value = best_links.get(field_name)
		if not value:
			continue
		return {
			"aftermarket_footprint": True,
			"parts_page": value if field_name == "parts_page" else None,
			"service_page": value if field_name == "service_page" else None,
			"support_page": value if field_name == "support_page" else None,
			"customer_portal_page": value if field_name == "customer_portal_page" else None,
			"portal_detected": field_name == "customer_portal_page",
			"aftermarket_reason": reason,
		}
	return _default_aftermarket()


def _has_strong_aftermarket_signal(result: dict[str, Any]) -> bool:
	return bool(
		result.get("parts_page")
		or result.get("service_page")
		or result.get("support_page")
		or result.get("customer_portal_page")
	)


def _has_primary_aftermarket_signal(result: dict[str, Any]) -> bool:
	return any(result.get(category) for category in PRIMARY_AFTERMARKET_CATEGORIES)


def _best_aftermarket_result(results: list[dict[str, Any]]) -> dict[str, Any]:
	best_result: dict[str, Any] | None = None
	best_score = -1
	for result in results:
		score = sum(1 for key in ("parts_page", "service_page", "support_page", "customer_portal_page") if result.get(key))
		if result.get("customer_portal_page"):
			score += 1
		if score > best_score:
			best_result = result
			best_score = score
	return best_result or _default_aftermarket()


def detect_aftermarket(resolved_domain: str, website_url: str | None = None) -> dict:
	try:
		candidate_domains = _candidate_domains(resolved_domain, website_url)
		if not candidate_domains:
			return _default_aftermarket()

		candidate_results: list[dict[str, Any]] = []
		for domain in candidate_domains:
			homepage_links = fetch_links_from_homepage(domain)
			homepage_scored = score_links_for_aftermarket(_dedupe_links(homepage_links))
			homepage_best_links = _pick_best_links(homepage_scored)

			if _has_primary_aftermarket_signal(homepage_best_links):
				return _first_clue_result(homepage_best_links)

			probed_links = _probe_common_aftermarket_paths(domain)
			combined_fast_links = _pick_best_links(score_links_for_aftermarket(_dedupe_links(homepage_links + probed_links)))
			if _has_primary_aftermarket_signal(combined_fast_links):
				return _first_clue_result(combined_fast_links)

			best_links = combined_fast_links
			if not _has_strong_aftermarket_signal(best_links):
				sitemap_links = fetch_links_from_sitemap(domain)
				all_links = _dedupe_links(homepage_links + probed_links + sitemap_links)
				scored_links = score_links_for_aftermarket(all_links)
				best_links = _pick_best_links(scored_links)

			candidate_results.append(_first_clue_result(best_links))
			if _has_strong_aftermarket_signal(best_links):
				return _first_clue_result(best_links)

		return _best_aftermarket_result(candidate_results)
	except Exception as exc:
		logger.warning("detect_aftermarket failed for %s: %s", resolved_domain, exc)
		return _default_aftermarket()
