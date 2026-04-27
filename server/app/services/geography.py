from __future__ import annotations

import re
from typing import Any

TARGET_NORTH_AMERICA = {
	"united states",
	"usa",
	"u.s.a",
	"u.s.",
	"us",
	"canada",
}

TARGET_EUROPE = {
	"united kingdom",
	"uk",
	"great britain",
	"england",
	"germany",
	"france",
	"italy",
	"spain",
	"netherlands",
	"belgium",
	"sweden",
	"norway",
	"denmark",
	"finland",
	"switzerland",
	"austria",
	"ireland",
	"poland",
	"portugal",
	"czech republic",
	"czechia",
	"hungary",
	"romania",
	"greece",
	"luxembourg",
}

TARGET_JAPAN = {"japan"}
FLAGGED_CHINA = {"china", "people's republic of china", "prc"}


def _normalize_country(value: Any) -> str:
	text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
	return text


def classify_hq_geography(hq_country: Any) -> dict[str, Any]:
	country = _normalize_country(hq_country)
	if not country:
		return {
			"hq_geography_flag": "unknown",
			"hq_geography_region": "Unknown",
			"hq_geography_reason": "hq_country missing",
		}

	if country in TARGET_NORTH_AMERICA:
		return {
			"hq_geography_flag": "target_market",
			"hq_geography_region": "North America",
			"hq_geography_reason": "Derived from hq_country",
		}
	if country in TARGET_EUROPE:
		return {
			"hq_geography_flag": "target_market",
			"hq_geography_region": "Europe",
			"hq_geography_reason": "Derived from hq_country",
		}
	if country in TARGET_JAPAN:
		return {
			"hq_geography_flag": "target_market",
			"hq_geography_region": "Japan",
			"hq_geography_reason": "Derived from hq_country",
		}
	if country in FLAGGED_CHINA:
		return {
			"hq_geography_flag": "flagged_market",
			"hq_geography_region": "China",
			"hq_geography_reason": "Derived from hq_country",
		}
	return {
		"hq_geography_flag": "non_target_market",
		"hq_geography_region": "Other",
		"hq_geography_reason": "Derived from hq_country",
	}
