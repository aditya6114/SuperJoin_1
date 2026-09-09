from typing import Optional, List
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from superjoin.api.service import KnowledgeLayerService, get_knowledge_service
from superjoin.api.schemas import (
    DocumentProcessResponse,
    DocumentResultsResponse,
    CorpusResultsResponse,
    ErrorResponse
)
from superjoin.ingestion.exceptions import InvalidDocumentError

router = APIRouter(tags=["Documents"])


@router.post(
    "/documents",
    response_model=DocumentProcessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a document PDF",
    description=(
        "Uploads a PDF document, validates integrity, runs ingestion (Docling layout parsing), "
        "runs fact extraction (Module 2), executes cross-document fact matching (Module 4), "
        "and evaluates relationship and conflict reasoning (Module 5)."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid PDF file or format"},
        500: {"model": ErrorResponse, "description": "Processing pipeline error"}
    }
)
async def upload_document(
    file: UploadFile = File(..., description="PDF file to ingest"),
    service: KnowledgeLayerService = Depends(get_knowledge_service)
):
    filename = file.filename or "uploaded_document.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_FILE_TYPE", "message": f"File '{filename}' must be a PDF."}
        )

    content = await file.read()
    if not content or len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMPTY_FILE", "message": "Uploaded file is empty."}
        )

    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_PDF_SIGNATURE", "message": "File does not contain a valid PDF signature."}
        )

    target_path = service.input_dir / filename
    try:
        with open(target_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "FILE_SAVE_ERROR", "message": f"Failed to save file: {str(e)}"}
        )

    try:
        doc_id = service.process_document(target_path)
        return DocumentProcessResponse(
            document_id=doc_id,
            status="processed",
            message="Document processed successfully"
        )
    except InvalidDocumentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_DOCUMENT", "message": str(e)}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "PROCESSING_FAILED", "message": f"Pipeline execution failed: {str(e)}"}
        )


@router.get(
    "/documents/{document_id}/results",
    response_model=DocumentResultsResponse,
    summary="Inspect one document's facts and relationships",
    description="Exposes structured facts, source evidence citations, and relationships associated with a specific document.",
    responses={
        404: {"model": ErrorResponse, "description": "Document not found"}
    }
)
async def get_document_results(
    document_id: str,
    service: KnowledgeLayerService = Depends(get_knowledge_service)
):
    results = service.get_document_results(document_id)
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": f"Document '{document_id}' was not found."}
        )
    return results


@router.get(
    "/results",
    response_model=CorpusResultsResponse,
    summary="Inspect results across documents",
    description=(
        "Retrieves accumulated facts and cross-document relationships. "
        "Supports filtering by comma-separated document IDs (e.g. ?document_ids=doc_a,doc_b)."
    )
)
async def get_corpus_results(
    document_ids: Optional[str] = Query(None, description="Comma-separated document IDs (e.g. doc_a,doc_b)"),
    service: KnowledgeLayerService = Depends(get_knowledge_service)
):
    doc_id_list = [d.strip() for d in document_ids.split(",") if d.strip()] if document_ids else None
    return service.get_corpus_results(doc_id_list)
