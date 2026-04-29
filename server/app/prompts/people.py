import json


def build_people_title_prompt(
    company_name: str,
    resolved_domain: str,
    aftermarket_data: dict,
    enrichment_data: dict,
) -> str:
    return (
        "You are selecting the most reachable job title for B2B trade-show outreach when no named contact was found.\n"
        "Pick the single role most likely to exist AND respond — not the most senior theoretically possible.\n"
        "Prefer aftermarket, service, parts, sales, or business development functions over generic titles.\n"
        "Scale title seniority to company size: a 50-person firm won't have a Chief Aftermarket Officer.\n"
        "Return JSON only: {\"suggested_title\": \"...\", \"reasoning\": \"...\"}\n\n"
        f"Company: {company_name}\n"
        f"Domain: {resolved_domain}\n"
        f"Aftermarket signals: {json.dumps(aftermarket_data, ensure_ascii=True)}\n"
        f"Enrichment data: {json.dumps(enrichment_data, ensure_ascii=True)}\n"
    )
