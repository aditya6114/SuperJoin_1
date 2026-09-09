from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from superjoin.api.service import KnowledgeLayerService, get_knowledge_service
from superjoin.api.schemas import RelationshipsListResponse, RelationshipModel, ErrorResponse

router = APIRouter(prefix="/relationships", tags=["Relationships"])


@router.get(
    "",
    response_model=RelationshipsListResponse,
    status_code=status.HTTP_200_OK,
    summary="List cross-document relationships",
    description=(
        "Retrieves relationships between facts across documents with actual embedded facts. "
        "Supports filtering by relationship_type (CORROBORATES, CONTRADICTS, CONTEXTUALLY_RECONCILED, etc.) "
        "and comma-separated document_ids."
    ),
)
async def list_relationships(
    relationship_type: Optional[str] = Query(
        None,
        description="Filter by type: CORROBORATES | CONTRADICTS | CONTEXTUALLY_RECONCILED | UNRELATED | UNRESOLVED"
    ),
    document_ids: Optional[str] = Query(
        None,
        description="Filter by comma-separated document IDs (e.g. doc_a,doc_b)"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of relationships to return"),
    offset: int = Query(0, ge=0, description="Number of relationships to skip"),
    service: KnowledgeLayerService = Depends(get_knowledge_service)
):
    doc_id_list = [d.strip() for d in document_ids.split(",") if d.strip()] if document_ids else None
    return service.get_relationships(
        relationship_type=relationship_type,
        document_ids=doc_id_list,
        limit=limit,
        offset=offset
    )


@router.get(
    "/{relationship_id}",
    response_model=RelationshipModel,
    status_code=status.HTTP_200_OK,
    summary="Get relationship by ID",
    description="Retrieves an individual relationship by its UUID with actual embedded facts.",
    responses={
        404: {"model": ErrorResponse, "description": "Relationship not found"}
    }
)
async def get_relationship(
    relationship_id: str,
    service: KnowledgeLayerService = Depends(get_knowledge_service)
):
    rel = service.get_relationship_by_id(relationship_id)
    if not rel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RELATIONSHIP_NOT_FOUND", "message": f"Relationship '{relationship_id}' was not found."}
        )
    return rel
