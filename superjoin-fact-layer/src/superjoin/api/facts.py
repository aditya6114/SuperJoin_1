from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from superjoin.api.service import KnowledgeLayerService, get_knowledge_service
from superjoin.api.schemas import FactsListResponse, FactModel, ErrorResponse

router = APIRouter(prefix="/facts", tags=["Facts"])


@router.get(
    "",
    response_model=FactsListResponse,
    status_code=status.HTTP_200_OK,
    summary="List extracted facts",
    description=(
        "Retrieves structured facts across the corpus or for a specific document. "
        "Supports filtering by document_id and predicate, along with pagination."
    ),
)
async def list_facts(
    document_id: Optional[str] = Query(None, description="Filter by document ID (e.g. 01-delhivery-prospectus-2022-excerpt-0d7e71)"),
    predicate: Optional[str] = Query(None, description="Filter by exact predicate (e.g. equity_share_capital, revenue_for_services)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of facts to return"),
    offset: int = Query(0, ge=0, description="Number of facts to skip"),
    service: KnowledgeLayerService = Depends(get_knowledge_service)
):
    return service.get_facts(
        document_id=document_id,
        predicate=predicate,
        limit=limit,
        offset=offset
    )


@router.get(
    "/{fact_id}",
    response_model=FactModel,
    status_code=status.HTTP_200_OK,
    summary="Get fact by ID",
    description="Retrieves an individual atomic fact with its source evidence citations.",
    responses={
        404: {"model": ErrorResponse, "description": "Fact not found"}
    }
)
async def get_fact(
    fact_id: str,
    service: KnowledgeLayerService = Depends(get_knowledge_service)
):
    fact = service.get_fact_by_id(fact_id)
    if not fact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "FACT_NOT_FOUND", "message": f"Fact '{fact_id}' was not found."}
        )
    return fact
