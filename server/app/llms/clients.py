from __future__ import annotations

import logging
import os
import time
from typing import Any

from app.config import GEMINI_API_KEY, GEMINI_API_KEYS, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL

GEMINI_DEFAULT_MODEL = GEMINI_MODEL
GROQ_DEFAULT_MODEL = GROQ_MODEL
OPENING_LINE_PRIMARY_GROQ_MODEL = os.getenv("OPENING_LINE_PRIMARY_GROQ_MODEL", "qwen/qwen3-32b").strip() or "qwen/qwen3-32b"
OPENING_LINE_SECONDARY_GROQ_MODEL = os.getenv("OPENING_LINE_SECONDARY_GROQ_MODEL", GROQ_DEFAULT_MODEL).strip() or GROQ_DEFAULT_MODEL
logger = logging.getLogger(__name__)

try:
	from langchain_google_genai import ChatGoogleGenerativeAI
	from langchain_groq import ChatGroq 
	HAS_LLM = True
except Exception:
	ChatGoogleGenerativeAI = ChatGroq = None  
	HAS_LLM = False


def _extract_status_code(exc: Exception) -> int | None:
	status_code = getattr(exc, "status_code", None)
	if isinstance(status_code, int):
		return status_code

	response = getattr(exc, "response", None)
	response_status = getattr(response, "status_code", None) if response is not None else None
	if isinstance(response_status, int):
		return response_status

	return None


def _is_retryable_llm_error(exc: Exception) -> bool:
	message = str(exc).lower()
	status_code = _extract_status_code(exc)
	return status_code == 429 or any(
		phrase in message
		for phrase in (
			"rate limit",
			"resource exhausted",
			"too many requests",
			"quota exceeded",
		)
	)


class _MultiKeyLLM:
	def __init__(self, llms: list[Any], label: str) -> None:
		self._llms = llms
		self._label = label

	def invoke(self, payload: Any) -> Any:
		last_error: Exception | None = None
		for index, llm in enumerate(self._llms, start=1):
			try:
				return llm.invoke(payload)
			except Exception as exc:
				last_error = exc
				if _is_retryable_llm_error(exc):
					logger.warning("[%s] key %s/%s exhausted or rate-limited; trying next key", self._label, index, len(self._llms))
					continue
				raise
		if last_error is not None:
			raise last_error
		raise RuntimeError(f"[{self._label}] no LLM instances available")

	def bind_tools(self, tools: list[Any]) -> "_MultiKeyLLM":
		bound_llms = [llm.bind_tools(tools) for llm in self._llms]
		return _MultiKeyLLM(bound_llms, f"{self._label}:bound")


def build_gemini_llm(*, model: str | None = None, temperature: float = 0, response_mime_type: str | None = None) -> Any:
	if not (HAS_LLM and ChatGoogleGenerativeAI is not None and GEMINI_API_KEYS):
		return None

	def _build_for_key(api_key: str) -> Any:
		kwargs: dict[str, Any] = {
			"model": model or GEMINI_DEFAULT_MODEL,
			"google_api_key": api_key,
			"temperature": temperature,
		}
		if response_mime_type:
			kwargs["response_mime_type"] = response_mime_type
		return ChatGoogleGenerativeAI(**kwargs)

	llms = [_build_for_key(api_key) for api_key in GEMINI_API_KEYS]
	if not llms:
		return None
	if len(llms) == 1:
		return llms[0]
	return _MultiKeyLLM(llms, "gemini")


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


def invoke_llm_with_retry(
	llm: Any,
	payload: Any,
	*,
	label: str = "llm",
	max_attempts: int = 3,
	base_delay_seconds: float = 0.75,
	fallback_llm: Any | None = None,
) -> Any | None:
	if llm is None:
		return None

	last_error: Exception | None = None
	for attempt in range(1, max_attempts + 1):
		try:
			return llm.invoke(payload)
		except Exception as exc:
			last_error = exc
			if attempt >= max_attempts or not _is_retryable_llm_error(exc):
				break
			delay = base_delay_seconds * (2 ** (attempt - 1))
			logger.warning("[%s] rate-limited on attempt %s/%s; retrying in %.2fs: %s", label, attempt, max_attempts, delay, exc)
			time.sleep(delay)

	if fallback_llm is not None and fallback_llm is not llm:
		try:
			return fallback_llm.invoke(payload)
		except Exception as exc:
			last_error = exc

	if last_error is not None:
		logger.warning("[%s] LLM invocation failed after retries: %s", label, last_error)
	return None
