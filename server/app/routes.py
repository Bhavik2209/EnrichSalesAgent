import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models import ResearchRequest, ResearchResponse
from app.services import synthesizer

router = APIRouter()


def _event_now() -> str:
	return datetime.now(timezone.utc).isoformat()


@router.post("/research", responses={500: {"description": "Internal Server Error"}})
async def research(payload: ResearchRequest) -> ResearchResponse:
	try:
		research_company = getattr(synthesizer, "research_company", None)
		if research_company is None:
			raise HTTPException(status_code=500, detail="research_company is not implemented yet")

		result = await research_company(
			company_name=payload.company_name,
			extra_context=payload.extra_context or "",
		)
		if isinstance(result, ResearchResponse):
			return result
		if isinstance(result, dict):
			return ResearchResponse(**result)
		raise HTTPException(status_code=500, detail="Invalid response from research service")
	except HTTPException:
		raise
	except Exception as exc:
		raise HTTPException(status_code=500, detail=f"Research failed: {exc}") from exc


@router.post("/research/stream", responses={500: {"description": "Internal Server Error"}})
async def research_stream(payload: ResearchRequest) -> StreamingResponse:
	queue: asyncio.Queue[dict] = asyncio.Queue()
	loop = asyncio.get_running_loop()

	def emit(stage: str, status: str, message: str, data: dict | None = None) -> None:
		event = {
			"type": "progress",
			"timestamp": _event_now(),
			"stage": stage,
			"status": status,
			"message": message,
		}
		if isinstance(data, dict) and data:
			event["data"] = data
		loop.call_soon_threadsafe(queue.put_nowait, event)

	async def runner() -> None:
		try:
			result = await synthesizer.research_company(
				company_name=payload.company_name,
				extra_context=payload.extra_context or "",
				progress_cb=emit,
			)
			payload_dict = result.model_dump() if isinstance(result, ResearchResponse) else result
			loop.call_soon_threadsafe(
				queue.put_nowait,
				{
					"type": "result",
					"timestamp": _event_now(),
					"payload": payload_dict,
				},
			)
		except Exception as exc:
			loop.call_soon_threadsafe(
				queue.put_nowait,
				{
					"type": "error",
					"timestamp": _event_now(),
					"message": f"Research failed: {exc}",
				},
			)

	async def stream() -> AsyncIterator[str]:
		task = asyncio.create_task(runner())
		try:
			while True:
				event = await queue.get()
				yield json.dumps(event, ensure_ascii=True) + "\n"
				if event.get("type") in {"result", "error"}:
					break
		finally:
			await task

	return StreamingResponse(stream(), media_type="application/x-ndjson")
