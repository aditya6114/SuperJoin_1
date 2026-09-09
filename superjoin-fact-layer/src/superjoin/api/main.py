from fastapi import FastAPI, Request, status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from superjoin.api.schemas import HealthResponse, ErrorResponse
from superjoin.api.documents import router as documents_router
from superjoin.api.facts import router as facts_router
from superjoin.api.relationships import router as relationships_router
from superjoin.api.query import router as query_router

OPENAPI_DESCRIPTION = """
## Superjoin Fact Knowledge Layer API

A production-quality REST API exposing the multi-module Fact Knowledge Layer:
- **Module 1 — Ingestion & Canonicalization**: Parse PDFs into geometry-normalized, provenance-preserving canonical documents.
- **Module 2 — Hybrid Fact Extraction**: Extract atomic, validated claims grounded in source evidence.
- **Module 4 — Fact Matching**: Cross-document fact indexing and deterministic claim comparison.
- **Module 5 — Relationship & Conflict Reasoning**: Evaluates semantic relations and conflicts between claims.

---

### Relationship Semantics

The relationship layer classifies pairs of facts into five precise categories:

- `CORROBORATES`: Independent or repeated evidence supports the same factual claim with equivalent or compatible values.
- `CONTRADICTS`: Same claim context (entity, metric, and period) but materially incompatible or conflicting values.
- `CONTEXTUALLY_RECONCILED`: Apparent differences explained by distinct time periods, operational scopes, accounting dimensions, or status definitions.
- `UNRESOLVED`: Insufficient contextual evidence or ambiguous entity attribution to safely determine relationship.
- `UNRELATED`: Claims describe distinct entities, non-comparable metrics, or incompatible fact types.
"""

TAGS_METADATA = [
    {
        "name": "System",
        "description": "Service health check and operational status endpoints.",
    },
    {
        "name": "Documents",
        "description": "PDF document upload, ingestion orchestration, and canonical metadata retrieval.",
    },
    {
        "name": "Facts",
        "description": "Atomic fact retrieval with detailed source evidence provenance (page numbers, element citations, text).",
    },
    {
        "name": "Relationships",
        "description": "Cross-document fact relationships, corroboration, contradictions, and reconciliations.",
    },
    {
        "name": "Query",
        "description": "Evidence-grounded natural language search and conflict resolution engine.",
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


# Exception Handlers ensuring consistent ErrorResponse envelope
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
        error_payload = exc.detail
    else:
        code_map = {
            status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
            status.HTTP_404_NOT_FOUND: "NOT_FOUND",
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: "PAYLOAD_TOO_LARGE",
            status.HTTP_422_UNPROCESSABLE_ENTITY: "UNPROCESSABLE_ENTITY",
            status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_SERVER_ERROR",
        }
        code = code_map.get(exc.status_code, "HTTP_ERROR")
        error_payload = {
            "code": code,
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
                "message": "Invalid request parameters or payload.",
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


# System Health Endpoints
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check",
    description="Returns the operational health status of the Superjoin Fact Layer API."
)
@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check (API v1)",
    description="Returns the operational health status of the Superjoin Fact Layer API."
)
async def health_check():
    return HealthResponse(status="ok", service="superjoin-fact-layer")


# Mount API v1 Routers
app.include_router(documents_router, prefix="/api/v1")
app.include_router(facts_router, prefix="/api/v1")
app.include_router(relationships_router, prefix="/api/v1")
app.include_router(query_router, prefix="/api/v1")
