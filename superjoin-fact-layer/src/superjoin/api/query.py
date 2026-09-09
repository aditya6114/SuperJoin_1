from fastapi import APIRouter, Depends, status

from superjoin.api.dependencies import get_app_service
from superjoin.api.schemas import QueryRequest, QueryResponse, FactItemResponse, RelationshipItemResponse
from superjoin.application import KnowledgeLayerApplication

router = APIRouter(prefix="/query", tags=["Query"])


@router.post(
    "",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Natural language query / fact-checking across knowledge layer",
    description=(
        "Executes a deterministic, evidence-grounded search across extracted facts and relationships. "
        "Answers factual inquiries, detects corroborations, exposes contradictions and discrepancies, "
        "and handles ambiguous or unresolved cases honestly without hallucination."
    )
)
async def query_knowledge_layer(
    request: QueryRequest,
    app_service: KnowledgeLayerApplication = Depends(get_app_service)
):
    result = app_service.query_knowledge_layer(
        query=request.query,
        document_ids=request.document_ids
    )

    facts = [FactItemResponse(**f) for f in result.get("facts", [])]
    relationships = [RelationshipItemResponse(**r) for r in result.get("relationships", [])]

    return QueryResponse(
        query=result["query"],
        status=result["status"],
        answer=result["answer"],
        facts=facts,
        relationships=relationships
    )
