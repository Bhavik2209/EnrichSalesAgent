import json


def build_people_title_prompt(
	company_name: str,
	resolved_domain: str,
	aftermarket_data: dict,
	enrichment_data: dict,
) -> str:
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
