from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict, model_validator
from superjoin.extraction.models import FactSubject, FactObject, TemporalContext


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = Field(default="ok", examples=["ok"])
    service: str = Field(default="superjoin-fact-layer", examples=["superjoin-fact-layer"])


class DocumentResponse(BaseModel):
    """Metadata summary of a document in the knowledge layer."""
    document_id: str = Field(..., description="Deterministic document identifier.", examples=["01-delhivery-prospectus-2022-excerpt-0d7e71"])
    filename: str = Field(..., description="Original filename of the document.", examples=["annual_report.pdf"])
    status: str = Field(default="processed", description="Document processing status.", examples=["processed"])
    page_count: int = Field(default=0, description="Total number of pages.", examples=[100])
    fact_count: int = Field(default=0, description="Total number of validated facts extracted.", examples=[822])
    relationship_count: Optional[int] = Field(default=None, description="Number of relationships involving this document.", examples=[45])
    created_at: Optional[str] = Field(default=None, description="Timestamp when the document was registered.")


class DocumentListResponse(BaseModel):
    """Paginated collection of documents."""
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int


class EvidenceDetail(BaseModel):
    """Resolved provenance citation for an extracted fact."""
    evidence_id: str = Field(..., description="Source element or bounding box identifier.")
    page: Optional[int] = Field(None, description="Page number containing the evidence.", examples=[17])
    text: Optional[str] = Field(None, description="Source excerpt text directly from CanonicalDocument.", examples=["Revenue for FY2024 was ₹500 crore."])


class FactItemResponse(BaseModel):
    """Complete representation of an atomic fact with resolved source provenance."""
    fact_id: str = Field(..., description="Unique fact UUID.")
    document_id: Optional[str] = Field(None, description="Document ID the fact was extracted from.")
    fact_type: str = Field(..., description="Claim category: 'numerical', 'semantic', 'event', 'attribute', 'relationship'.")
    subject: FactSubject = Field(..., description="Entity subject.")
    predicate: str = Field(..., description="Predicate relationship or metric.")
    object: FactObject = Field(..., description="Structured object value, currency, unit, and scale.")
    time: TemporalContext = Field(..., description="Temporal grounding.")
    scope: Optional[str] = Field(None, description="Contextual or geographic scope.")
    qualifiers: List[str] = Field(default_factory=list, description="Semantic qualifiers.")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0.")
    evidence_ids: List[str] = Field(default_factory=list, description="Raw element IDs.")
    evidence: List[EvidenceDetail] = Field(default_factory=list, description="Resolved evidence citations with page and text.")


class FactListResponse(BaseModel):
    """Paginated collection of facts."""
    items: List[FactItemResponse]
    total: int
    page: int
    page_size: int


class RelationshipItemResponse(BaseModel):
    """Semantic relationship or conflict between two facts."""
    model_config = ConfigDict(populate_by_name=True)

    relationship_id: str = Field(..., description="Unique relationship identifier.")
    relationship_type: str = Field(
        ...,
        description="CORROBORATES | CONTRADICTS | CONTEXTUALLY_RECONCILED | UNRELATED | UNRESOLVED"
    )
    relationship: Optional[str] = Field(None, description="Relationship type compatibility field.")
    confidence: float = Field(..., description="Deterministic confidence score between 0.0 and 1.0.")
    source_independence: str = Field(..., description="'cross_document' or 'same_document'")
    reason: str = Field(..., description="Concise deterministic summary reason.")
    explanation: str = Field(..., description="Detailed explanation grounded in structured signals.")
    fact_a_id: str = Field(..., description="Fact A ID.")
    fact_b_id: str = Field(..., description="Fact B ID.")
    document_a_id: Optional[str] = Field(None, description="Document A ID.")
    document_b_id: Optional[str] = Field(None, description="Document B ID.")
    fact_a: Optional[Any] = Field(None, description="Complete Fact A.")
    fact_b: Optional[Any] = Field(None, description="Complete Fact B.")
    evidence_a: List[EvidenceDetail] = Field(default_factory=list, description="Resolved evidence for Fact A.")
    evidence_b: List[EvidenceDetail] = Field(default_factory=list, description="Resolved evidence for Fact B.")

    @model_validator(mode="before")
    @classmethod
    def normalize_relationship_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            rel = data.get("relationship_type") or data.get("relationship")
            if rel:
                rel_val = rel.value if hasattr(rel, "value") else str(rel)
                data["relationship_type"] = rel_val
                data["relationship"] = rel_val
        return data


class RelationshipListResponse(BaseModel):
    """Paginated collection of semantic relationships."""
    items: List[RelationshipItemResponse]
    total: int
    page: int
    page_size: int


class QueryRequest(BaseModel):
    """User query request for evidence-grounded answers."""
    query: str = Field(..., description="Natural language query or conflict inquiry.", examples=["Are there conflicting revenue figures for FY2024?"])
    document_ids: Optional[List[str]] = Field(None, description="Optional document ID filter scope.", examples=[["01-delhivery-prospectus-2022-excerpt-0d7e71"]])


class QueryResponse(BaseModel):
    """Structured, evidence-grounded response to a user query."""
    query: str
    status: str = Field(..., description="'answered' | 'no_results' | 'ambiguous'", examples=["answered"])
    answer: str = Field(..., description="Direct evidence-grounded summary answer.")
    facts: List[FactItemResponse] = Field(default_factory=list, description="Underlying grounded facts.")
    relationships: List[RelationshipItemResponse] = Field(default_factory=list, description="Relevant relationships and conflicts.")


class ErrorDetail(BaseModel):
    """Standardized error envelope payload."""
    code: str = Field(..., examples=["DOCUMENT_NOT_FOUND"])
    message: str = Field(..., examples=["Document 'doc_123' was not found."])
    details: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Consistent API error response."""
    error: ErrorDetail
