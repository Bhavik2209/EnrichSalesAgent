import json


def build_opening_line_prompt(company_name: str, data: dict) -> str:
	context = {
		"official_name": data.get("official_name"),
		"description": data.get("description"),
		"industry": data.get("industry"),
		"what_they_make": data.get("what_they_make"),
		"hq_country": data.get("hq_country"),
		"hq_city": data.get("hq_city"),
		"parent_company": data.get("parent_company"),
		"aftermarket_footprint": data.get("aftermarket_footprint"),
		"recent_news_titles": data.get("recent_news_titles") or [],
	}
	return (
		"You write short B2B outreach opening lines for sales research.\n"
		"Using only the structured company context below, write one personalized opening line.\n"
		"Return JSON only with exactly one key: personalized_opening_line.\n"
		"Requirements:\n"
		"- One sentence only.\n"
		"- 22 to 38 words.\n"
		"- Sound natural and specific, not robotic.\n"
		"- Use the strongest concrete signal available such as what the company makes, industry, parent company, or recent news.\n"
		"- Do not repeat awkward Wikidata labels like 'United States manufacturing company' or generic phrases like 'is focused on'.\n"
		"- End by connecting to service, aftermarket, parts, support, or digital transformation.\n"
		"- Do not invent facts.\n\n"
		f"Company: {company_name}\n"
		f"Context: {json.dumps(context, ensure_ascii=True)}"
	)


def build_synthesis_prompt(company_name: str, missing_fields: list[str], combined_text: str) -> str:
	return (
		"You are extracting company information. Using only the text below,\n"
		"fill in the missing fields. Return valid JSON only, no markdown.\n"
		"If a field cannot be determined from the text, return null for it.\n\n"
		f"Company: {company_name}\n"
		f"Missing fields to fill: {missing_fields}\n\n"
		"SOURCE TEXT:\n"
		f"{combined_text[:6000]}"
	)
