from __future__ import annotations

import os
from typing import Any

from app.config import GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL

GEMINI_DEFAULT_MODEL = GEMINI_MODEL
GROQ_DEFAULT_MODEL = GROQ_MODEL
OPENING_LINE_PRIMARY_GROQ_MODEL = os.getenv("OPENING_LINE_PRIMARY_GROQ_MODEL", "qwen/qwen3-32b").strip() or "qwen/qwen3-32b"
OPENING_LINE_SECONDARY_GROQ_MODEL = os.getenv("OPENING_LINE_SECONDARY_GROQ_MODEL", GROQ_DEFAULT_MODEL).strip() or GROQ_DEFAULT_MODEL

try:
	from langchain_google_genai import ChatGoogleGenerativeAI
	from langchain_groq import ChatGroq 
	HAS_LLM = True
except Exception:
	ChatGoogleGenerativeAI = ChatGroq = None  
	HAS_LLM = False


def build_gemini_llm(*, model: str | None = None, temperature: float = 0, response_mime_type: str | None = None) -> Any:
	if not (HAS_LLM and GEMINI_API_KEY and ChatGoogleGenerativeAI is not None):
		return None
	kwargs: dict[str, Any] = {
		"model": model or GEMINI_DEFAULT_MODEL,
		"google_api_key": GEMINI_API_KEY,
		"temperature": temperature,
	}
	if response_mime_type:
		kwargs["response_mime_type"] = response_mime_type
	return ChatGoogleGenerativeAI(**kwargs)


def build_groq_llm(*, model: str | None = None, temperature: float = 0) -> Any:
	if not (HAS_LLM and GROQ_API_KEY and ChatGroq is not None):
		return None
	return ChatGroq(model=model or GROQ_DEFAULT_MODEL, groq_api_key=GROQ_API_KEY, temperature=temperature)


def build_default_llm(*, temperature: float = 0) -> Any:
	llm = build_gemini_llm(temperature=temperature)
	if llm is not None:
		return llm
	return build_groq_llm(temperature=temperature)


def build_default_json_llm(*, temperature: float = 0) -> Any:
	llm = build_gemini_llm(temperature=temperature, response_mime_type="application/json")
	if llm is not None:
		return llm
	return build_groq_llm(temperature=temperature)
