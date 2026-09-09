from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from superjoin.api.dependencies import get_app_service
from superjoin.api.schemas import FactItemResponse, FactListResponse, ErrorResponse
from superjoin.application import KnowledgeLayerApplication

router = APIRouter(tags=["Facts"])


@router.get(
    "/documents/{document_id}/facts",
    response_model=FactListResponse,
    summary="Retrieve extracted facts for a document",
    description=(
        "Returns validated, atomic facts extracted from the document with full source evidence "
        "and provenance (page numbers, element citations, excerpt text). Supports pagination and filters."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Document not found"}
    }
)
async def get_document_facts(
    document_id: str,
    fact_type: Optional[str] = Query(None, description="Filter by fact type (e.g. 'numerical', 'semantic')"),
    subject: Optional[str] = Query(None, description="Filter by subject entity name"),
    predicate: Optional[str] = Query(None, description="Filter by predicate or metric"),
    page_num: Optional[int] = Query(None, alias="page_number", description="Filter facts on a specific PDF page"),
    page: int = Query(1, ge=1, description="Pagination page index"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    app_service: KnowledgeLayerApplication = Depends(get_app_service)
):
    # Check if document exists in parsed or facts
    doc_info = app_service.get_document(document_id)
    fact_file = app_service.facts_dir / f"{document_id}.json"
    if not doc_info and not fact_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": f"Document '{document_id}' was not found."}
        )

    items, total = app_service.get_facts_for_document(
        document_id=document_id,
        fact_type=fact_type,
        subject=subject,
        predicate=predicate,
        page_filter=page_num,
        page=page,
        page_size=page_size
    )

    return FactListResponse(
        items=[FactItemResponse(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get(
    "/facts/{fact_id}",
    response_model=FactItemResponse,
    summary="Retrieve an individual fact with complete provenance",
    description=(
        "Returns the complete structured fact, its parent document ID, and source evidence citations "
        "(page number and source text) enabling full traceability from Fact -> Document -> Page -> Evidence."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Fact not found"}
    }
)
async def get_fact(
    fact_id: str,
    app_service: KnowledgeLayerApplication = Depends(get_app_service)
):
    fact_dict = app_service.get_fact_by_id(fact_id)
    if not fact_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "FACT_NOT_FOUND", "message": f"Fact '{fact_id}' was not found."}
        )
    return FactItemResponse(**fact_dict)
