from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResearchRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	company_name: str
	extra_context: str | None = None


class ResearchResponse(BaseModel):
	company_name: str | None = None
	resolved_domain: str | None = None
	data: dict[str, Any] = Field(default_factory=dict)
	field_sources: dict[str, Any] = Field(default_factory=dict)
	sources: list[str] = Field(default_factory=list)
	notes: list[str] = Field(default_factory=list)
