from fastapi import APIRouter, Depends, status

from superjoin.api.service import KnowledgeLayerService, get_knowledge_service
from superjoin.api.schemas import QueryRequest, QueryResponse

router = APIRouter(prefix="/query", tags=["Query"])


@router.post(
    "",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query Fact Knowledge Layer",
    description=(
        "Executes evidence-grounded search across the structured knowledge layer. "
        "Answers queries using extracted facts, surfaces corroborations and contradictions, "
        "and links directly to source evidence."
    )
)
async def query_knowledge_layer(
    request: QueryRequest,
    service: KnowledgeLayerService = Depends(get_knowledge_service)
):
    return service.query_knowledge_layer(
        query=request.query,
        document_ids=request.document_ids
    )
