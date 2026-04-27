from fastapi import APIRouter, HTTPException

from app.models import ResearchRequest, ResearchResponse
from app.services import synthesizer

router = APIRouter()


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
