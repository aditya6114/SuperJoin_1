import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from superjoin.api.dependencies import get_app_service, PaginationParams
from superjoin.api.schemas import DocumentResponse, DocumentListResponse, ErrorResponse
from superjoin.application import KnowledgeLayerApplication
from superjoin.ingestion.exceptions import InvalidDocumentError

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a document PDF",
    description=(
        "Uploads a PDF document, validates file integrity, executes layout ingestion (Docling), "
        "extracts atomic facts (Module 2), executes cross-document matching (Module 4), "
        "re-evaluates relationship reasoning (Module 5), and persists artifacts to storage."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid PDF file or format"},
        422: {"model": ErrorResponse, "description": "Unprocessable entity"},
        500: {"model": ErrorResponse, "description": "Processing pipeline error"}
    }
)
async def upload_document(
    file: UploadFile = File(..., description="PDF document file"),
    app_service: KnowledgeLayerApplication = Depends(get_app_service)
):
    # 1. Filename validation
    filename = file.filename or "uploaded_document.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_FILE_TYPE", "message": f"File '{filename}' must be a PDF."}
        )

    # 2. Read content & validate magic bytes
    content = await file.read()
    if not content or len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMPTY_FILE", "message": "The uploaded file is empty."}
        )

    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_PDF_SIGNATURE", "message": "File does not have a valid PDF header."}
        )

    # 3. Save to data/input
    target_path = app_service.input_dir / filename
    try:
        with open(target_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "FILE_SAVE_ERROR", "message": f"Failed to save uploaded file: {str(e)}"}
        )

    # 4. Invoke end-to-end processing pipeline
    try:
        summary = app_service.process_document(target_path)
        return DocumentResponse(**summary)
    except InvalidDocumentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_DOCUMENT", "message": str(e)}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "PROCESSING_FAILED", "message": f"Pipeline processing failed: {str(e)}"}
        )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List available documents",
    description="Retrieves a paginated list of all parsed canonical documents available in the knowledge layer."
)
async def list_documents(
    pagination: PaginationParams = Depends(),
    app_service: KnowledgeLayerApplication = Depends(get_app_service)
):
    items, total = app_service.list_documents(
        page=pagination.page,
        page_size=pagination.page_size
    )
    return DocumentListResponse(
        items=[DocumentResponse(**item) for item in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Retrieve document metadata",
    description="Returns metadata and processing summary for a specific document without dumping heavy canonical page content.",
    responses={
        404: {"model": ErrorResponse, "description": "Document not found"}
    }
)
async def get_document(
    document_id: str,
    app_service: KnowledgeLayerApplication = Depends(get_app_service)
):
    doc_info = app_service.get_document(document_id)
    if not doc_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": f"Document '{document_id}' was not found."}
        )
    return DocumentResponse(**doc_info)
