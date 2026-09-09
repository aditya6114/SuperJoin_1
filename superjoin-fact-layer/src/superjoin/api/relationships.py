from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from superjoin.api.dependencies import get_app_service
from superjoin.api.schemas import RelationshipItemResponse, RelationshipListResponse, ErrorResponse
from superjoin.application import KnowledgeLayerApplication
from superjoin.reasoning.models import RelationshipType

router = APIRouter(prefix="/relationships", tags=["Relationships"])


@router.get(
    "",
    response_model=RelationshipListResponse,
    summary="List cross-document relationships and conflicts",
    description=(
        "Retrieves reasoned relationships between facts across documents. "
        "Supports filtering by document_id, fact_id, relationship_type "
        "(CORROBORATES, CONTRADICTS, CONTEXTUALLY_RECONCILED, UNRELATED, UNRESOLVED), "
        "source independence, and minimum confidence."
    )
)
async def list_relationships(
    document_id: Optional[str] = Query(None, description="Filter relationships involving this document ID"),
    fact_id: Optional[str] = Query(None, description="Filter relationships involving this fact ID"),
    relationship_type: Optional[RelationshipType] = Query(None, description="Relationship category"),
    source_independence: Optional[str] = Query(None, description="'cross_document' or 'same_document'"),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    page: int = Query(1, ge=1, description="Page index"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
    app_service: KnowledgeLayerApplication = Depends(get_app_service)
):
    type_str = relationship_type.value if relationship_type else None
    items, total = app_service.get_relationships(
        document_id=document_id,
        fact_id=fact_id,
        relationship_type=type_str,
        source_independence=source_independence,
        confidence_min=confidence_min,
        page=page,
        page_size=page_size
    )

    return RelationshipListResponse(
        items=[RelationshipItemResponse(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get(
    "/{relationship_id}",
    response_model=RelationshipItemResponse,
    summary="Retrieve an individual relationship with full provenance",
    description=(
        "Returns the complete details of a specific relationship, including underlying Fact A, Fact B, "
        "source evidence citations, confidence score, and clear human-readable explanations."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Relationship not found"}
    }
)
async def get_relationship(
    relationship_id: str,
    app_service: KnowledgeLayerApplication = Depends(get_app_service)
):
    rel_dict = app_service.get_relationship_by_id(relationship_id)
    if not rel_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RELATIONSHIP_NOT_FOUND", "message": f"Relationship '{relationship_id}' was not found."}
        )
    return RelationshipItemResponse(**rel_dict)
