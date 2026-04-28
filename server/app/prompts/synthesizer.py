import json


def build_message_prompt(company_name: str, data: dict) -> str:
	context = {
		"official_name": data.get("official_name"),
		"description": data.get("description"),
		"industry": data.get("industry"),
		"what_they_make": data.get("what_they_make"),
		"company_tags": data.get("company_tags") or [],
		"hq_country": data.get("hq_country"),
		"hq_city": data.get("hq_city"),
		"parent_company": data.get("parent_company"),
		"aftermarket_footprint": data.get("aftermarket_footprint"),
		"recent_news_titles": data.get("recent_news_titles") or [],
	}
	return (
		"You write concise company messaging for sales research.\n"
		"Using only the structured company context below, write both a structured company summary and one personalized opening line.\n"
		"Return JSON only with exactly two keys: company_summary_short and personalized_opening_line.\n"
		"Requirements:\n"
		"- company_summary_short: exactly 5 or 6 short lines inside one JSON string, with each line separated by a newline character.\n"
		"- Each line should be concise, factual, and easy to read aloud.\n"
		"- Use the available company facts across the lines: what the company does, geography, industry, what it makes, company_tags, aftermarket footprint, and any useful parent-company or positioning context.\n"
		"- If company_tags are useful, include 2 to 4 of them naturally in one line.\n"
		"- Do not use markdown bullets, numbering, labels like 'Line 1', or a long paragraph.\n"
		"- personalized_opening_line: 1 sentence, 22 to 38 words, natural and specific.\n"
		"- personalized_opening_line should use the strongest concrete signal available such as what the company makes, industry, parent company, or recent news.\n"
		"- Do not repeat awkward Wikidata labels like 'United States manufacturing company' or generic phrases like 'is focused on'.\n"
		"- End the opening line by connecting to service, aftermarket, parts, support, or digital transformation.\n"
		"- Keep both outputs grounded in the provided context and do not invent facts.\n"
		"- Do not invent facts.\n\n"
		f"Company: {company_name}\n"
		f"Context: {json.dumps(context, ensure_ascii=True)}"
	)


def build_opening_line_prompt(company_name: str, data: dict) -> str:
	return build_message_prompt(company_name, data)


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
