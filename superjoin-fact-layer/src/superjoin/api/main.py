from fastapi import FastAPI, Request, status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from superjoin.api.schemas import HealthResponse
from superjoin.api.documents import router as documents_router
from superjoin.api.facts import router as facts_router
from superjoin.api.relationships import router as relationships_router
from superjoin.api.query import router as query_router

OPENAPI_DESCRIPTION = """
## Superjoin Fact Knowledge Layer API

A lightweight, production-quality API layer exposing the multi-module Fact Knowledge Layer:
- **Module 1 — Document Ingestion & Parsing**
- **Module 2 — Fact Extraction**
- **Module 4 — Fact Matching**
- **Module 5 — Relationship & Conflict Reasoning**

---

### Core Workflow:
1. `POST /api/v1/documents`: Upload and process PDF documents through Modules 1 → 2 → 4 → 5.
2. `GET /api/v1/facts`: Retrieve facts across documents with filtering and pagination.
3. `GET /api/v1/relationships`: Retrieve relationships between facts with actual embedded facts.
4. `GET /api/v1/documents/{document_id}/results`: Inspect atomic facts and relationships for a specific document.
5. `GET /api/v1/results`: Inspect facts and cross-document relationships across all or selected documents.
6. `POST /api/v1/query`: Query the structured knowledge layer for grounded facts and conflicts.
7. `GET /health`: Operational health check.
"""

TAGS_METADATA = [
    {
        "name": "System",
        "description": "Health check endpoints.",
    },
    {
        "name": "Documents",
        "description": "Document ingestion, results inspection, and cross-document retrieval.",
    },
    {
        "name": "Facts",
        "description": "Structured fact inspection, filtering, and retrieval.",
    },
    {
        "name": "Relationships",
        "description": "Cross-document relationships with actual embedded facts and conflict reasoning.",
    },
    {
        "name": "Query",
        "description": "Evidence-grounded query and conflict detection.",
    },
]

app = FastAPI(
    title="Superjoin Fact Knowledge Layer API",
    description=OPENAPI_DESCRIPTION,
    version="0.1.0",
    openapi_tags=TAGS_METADATA,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# Standardized Error Envelope Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
        error_payload = exc.detail
    else:
        code_map = {
            status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
            status.HTTP_404_NOT_FOUND: "NOT_FOUND",
            status.HTTP_422_UNPROCESSABLE_ENTITY: "UNPROCESSABLE_ENTITY",
            status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_SERVER_ERROR",
        }
        error_payload = {
            "code": code_map.get(exc.status_code, "HTTP_ERROR"),
            "message": str(exc.detail)
        }

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error_payload}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request parameters.",
                "details": exc.errors()
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected internal server error occurred."
            }
        }
    )


# Health Endpoints
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check",
    description="Returns simple operational status."
)
@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check (API v1)"
)
async def health_check():
    return HealthResponse(status="ok")


# Mount Routes under /api/v1
app.include_router(documents_router, prefix="/api/v1")
app.include_router(facts_router, prefix="/api/v1")
app.include_router(relationships_router, prefix="/api/v1")
app.include_router(query_router, prefix="/api/v1")

