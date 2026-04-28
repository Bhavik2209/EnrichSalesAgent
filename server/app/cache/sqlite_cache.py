from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from app.config import CACHE_DB_PATH, CACHE_TTL_SECONDS

logger = logging.getLogger(__name__)
_DB_LOCK = threading.Lock()
CACHE_KEY_VERSION = "v4"


def _get_connection() -> sqlite3.Connection:
	db_path = Path(CACHE_DB_PATH)
	db_path.parent.mkdir(parents=True, exist_ok=True)
	connection = sqlite3.connect(str(db_path))
	connection.execute(
		"""
		CREATE TABLE IF NOT EXISTS research_cache (
			cache_key TEXT PRIMARY KEY,
			company_name TEXT NOT NULL,
			payload_json TEXT NOT NULL,
			created_at INTEGER NOT NULL,
			expires_at INTEGER NOT NULL
		)
		"""
	)
	connection.execute(
		"""
		CREATE TABLE IF NOT EXISTS domain_research_cache (
			cache_key TEXT PRIMARY KEY,
			resolved_domain TEXT NOT NULL,
			payload_json TEXT NOT NULL,
			created_at INTEGER NOT NULL,
			expires_at INTEGER NOT NULL
		)
		"""
	)
	return connection


def _normalize_company_name(company_name: str) -> str:
	raw = str(company_name or "").strip().lower()
	raw = re.sub(r"[^a-z0-9]+", " ", raw)
	return " ".join(raw.split())


def _normalize_extra_context(extra_context: str) -> str:
	return " ".join(str(extra_context or "").strip().lower().split())


def _normalize_requested_fields(requested_fields: list[str] | None) -> list[str]:
	if not requested_fields:
		return []
	return sorted({str(field).strip() for field in requested_fields if str(field).strip()})


def _normalize_domain(domain: str) -> str:
	raw = str(domain or "").strip().lower()
	raw = re.sub(r"^https?://", "", raw)
	raw = raw.strip("/")
	return raw


def build_research_cache_key(
	company_name: str,
	extra_context: str = "",
	requested_fields: list[str] | None = None,
) -> str:
	key_payload = {
		"cache_version": CACHE_KEY_VERSION,
		"company_name": _normalize_company_name(company_name),
		"extra_context": _normalize_extra_context(extra_context),
		"requested_fields": _normalize_requested_fields(requested_fields),
	}
	return json.dumps(key_payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def build_domain_research_cache_key(
	resolved_domain: str,
	extra_context: str = "",
	requested_fields: list[str] | None = None,
) -> str:
	key_payload = {
		"cache_version": CACHE_KEY_VERSION,
		"resolved_domain": _normalize_domain(resolved_domain),
		"extra_context": _normalize_extra_context(extra_context),
		"requested_fields": _normalize_requested_fields(requested_fields),
	}
	return json.dumps(key_payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def get_cached_research_response(
	company_name: str,
	extra_context: str = "",
	requested_fields: list[str] | None = None,
) -> dict[str, Any] | None:
	cache_key = build_research_cache_key(company_name, extra_context, requested_fields)
	now_ts = int(time.time())
	with _DB_LOCK:
		try:
			connection = _get_connection()
			try:
				row = connection.execute(
					"SELECT payload_json, created_at, expires_at FROM research_cache WHERE cache_key = ?",
					(cache_key,),
				).fetchone()
				if row is None:
					return None

				payload_json, created_at, expires_at = row
				if int(expires_at) <= now_ts:
					connection.execute("DELETE FROM research_cache WHERE cache_key = ?", (cache_key,))
					connection.commit()
					return None

				payload = json.loads(str(payload_json))
				if not isinstance(payload, dict):
					return None
				age_seconds = max(0, now_ts - int(created_at))
				notes = payload.get("notes")
				if not isinstance(notes, list):
					notes = []
				notes = [str(item) for item in notes]
				notes.append(f"Cache hit sqlite age_seconds={age_seconds}")
				payload["notes"] = notes
				return payload
			finally:
				connection.close()
		except Exception as exc:
			logger.warning("SQLite cache read failed for %s: %s", company_name, exc)
			return None


def set_cached_research_response(
	company_name: str,
	extra_context: str,
	requested_fields: list[str] | None,
	payload: dict[str, Any],
) -> None:
	cache_key = build_research_cache_key(company_name, extra_context, requested_fields)
	now_ts = int(time.time())
	expires_at = now_ts + max(1, int(CACHE_TTL_SECONDS))
	with _DB_LOCK:
		try:
			connection = _get_connection()
			try:
				connection.execute(
					"""
					INSERT INTO research_cache (cache_key, company_name, payload_json, created_at, expires_at)
					VALUES (?, ?, ?, ?, ?)
					ON CONFLICT(cache_key) DO UPDATE SET
						company_name = excluded.company_name,
						payload_json = excluded.payload_json,
						created_at = excluded.created_at,
						expires_at = excluded.expires_at
					""",
					(
						cache_key,
						company_name,
						json.dumps(payload, ensure_ascii=True),
						now_ts,
						expires_at,
					),
				)
				connection.commit()
			finally:
				connection.close()
		except Exception as exc:
			logger.warning("SQLite cache write failed for %s: %s", company_name, exc)


def get_cached_research_response_by_domain(
	resolved_domain: str,
	extra_context: str = "",
	requested_fields: list[str] | None = None,
) -> dict[str, Any] | None:
	normalized_domain = _normalize_domain(resolved_domain)
	if not normalized_domain:
		return None
	cache_key = build_domain_research_cache_key(normalized_domain, extra_context, requested_fields)
	now_ts = int(time.time())
	with _DB_LOCK:
		try:
			connection = _get_connection()
			try:
				row = connection.execute(
					"SELECT payload_json, created_at, expires_at FROM domain_research_cache WHERE cache_key = ?",
					(cache_key,),
				).fetchone()
				if row is None:
					return None

				payload_json, created_at, expires_at = row
				if int(expires_at) <= now_ts:
					connection.execute("DELETE FROM domain_research_cache WHERE cache_key = ?", (cache_key,))
					connection.commit()
					return None

				payload = json.loads(str(payload_json))
				if not isinstance(payload, dict):
					return None
				age_seconds = max(0, now_ts - int(created_at))
				notes = payload.get("notes")
				if not isinstance(notes, list):
					notes = []
				notes = [str(item) for item in notes]
				notes.append(f"Cache hit domain={normalized_domain} age_seconds={age_seconds}")
				payload["notes"] = notes
				return payload
			finally:
				connection.close()
		except Exception as exc:
			logger.warning("SQLite domain cache read failed for %s: %s", normalized_domain, exc)
			return None


def set_cached_research_response_by_domain(
	resolved_domain: str,
	extra_context: str,
	requested_fields: list[str] | None,
	payload: dict[str, Any],
) -> None:
	normalized_domain = _normalize_domain(resolved_domain)
	if not normalized_domain:
		return
	cache_key = build_domain_research_cache_key(normalized_domain, extra_context, requested_fields)
	now_ts = int(time.time())
	expires_at = now_ts + max(1, int(CACHE_TTL_SECONDS))
	with _DB_LOCK:
		try:
			connection = _get_connection()
			try:
				connection.execute(
					"""
					INSERT INTO domain_research_cache (cache_key, resolved_domain, payload_json, created_at, expires_at)
					VALUES (?, ?, ?, ?, ?)
					ON CONFLICT(cache_key) DO UPDATE SET
						resolved_domain = excluded.resolved_domain,
						payload_json = excluded.payload_json,
						created_at = excluded.created_at,
						expires_at = excluded.expires_at
					""",
					(
						cache_key,
						normalized_domain,
						json.dumps(payload, ensure_ascii=True),
						now_ts,
						expires_at,
					),
				)
				connection.commit()
			finally:
				connection.close()
		except Exception as exc:
			logger.warning("SQLite domain cache write failed for %s: %s", normalized_domain, exc)
