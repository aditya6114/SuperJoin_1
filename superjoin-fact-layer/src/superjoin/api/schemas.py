from typing import Optional, List, Any, Union
from pydantic import BaseModel, Field, ConfigDict


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(default="ok", examples=["ok"])


class DocumentProcessResponse(BaseModel):
    """Response returned upon successful document upload and processing."""
    document_id: str = Field(..., description="Deterministic document identifier.", examples=["03-delhivery-q4-fy24-earnings-presentation-5ca307"])
    status: str = Field(default="processed", examples=["processed"])
    message: str = Field(default="Document processed successfully", examples=["Document processed successfully"])


class DocumentInfo(BaseModel):
    """Basic document metadata."""
    document_id: str = Field(..., examples=["doc_123"])
    filename: str = Field(..., examples=["annual_report.pdf"])


class EvidenceModel(BaseModel):
    """Evidence citation grounded in source document."""
    page: Optional[int] = Field(None, description="PDF page number containing evidence.", examples=[42])
    text: Optional[str] = Field(None, description="Verbatim source excerpt text.", examples=["Revenue was ₹500 crore..."])


class FactModel(BaseModel):
    """Clean representation of an extracted fact."""
    fact_id: str = Field(..., examples=["fact_001"])
    document_id: Optional[str] = Field(None, examples=["doc_123"])
    subject: str = Field(..., description="Entity name.", examples=["Delhivery"])
    predicate: str = Field(..., description="Predicate or metric.", examples=["revenue"])
    value: str = Field(..., description="Formatted object value with scale and currency.", examples=["₹500 crore"])
    period: Optional[str] = Field(None, description="Temporal period or date expression.", examples=["FY2024"])
    evidence: EvidenceModel


class RelationshipModel(BaseModel):
    """Clean representation of a relationship or conflict between two facts."""
    model_config = ConfigDict(populate_by_name=True)

    relationship_id: Optional[str] = Field(None, description="Unique relationship identifier.", examples=["rel_001"])
    fact_a: Union[FactModel, str] = Field(..., description="Fact A actual details or identifier.")
    fact_b: Union[FactModel, str] = Field(..., description="Fact B actual details or identifier.")
    type: str = Field(
        ...,
        description="Relationship type: CORROBORATES | CONTRADICTS | CONTEXTUALLY_RECONCILED | UNRELATED | UNRESOLVED",
        examples=["CONTRADICTS"]
    )
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0.", examples=[0.91])
    reason: str = Field(..., description="Deterministic reason.", examples=["Same subject, metric, period and scope but materially different values."])
    explanation: Optional[str] = Field(None, description="Detailed explanation of the relationship.")


class FactsListResponse(BaseModel):
    """Paginated list of facts."""
    total: int = Field(..., description="Total count of matching facts.", examples=[822])
    limit: int = Field(default=100, description="Page size limit.", examples=[100])
    offset: int = Field(default=0, description="Page offset.", examples=[0])
    facts: List[FactModel] = Field(default_factory=list)


class RelationshipsListResponse(BaseModel):
    """Paginated list of relationships with actual embedded facts."""
    total: int = Field(..., description="Total count of matching relationships.", examples=[45])
    limit: int = Field(default=100, description="Page size limit.", examples=[100])
    offset: int = Field(default=0, description="Page offset.", examples=[0])
    relationships: List[RelationshipModel] = Field(default_factory=list)


class DocumentResultsResponse(BaseModel):
    """Extracted facts and relationships associated with a single document."""
    document: DocumentInfo
    facts: List[FactModel] = Field(default_factory=list)
    relationships: List[RelationshipModel] = Field(default_factory=list)


class CorpusResultsResponse(BaseModel):
    """Accumulated facts and cross-document relationships across the corpus."""
    documents: List[DocumentInfo] = Field(default_factory=list)
    facts: List[FactModel] = Field(default_factory=list)
    relationships: List[RelationshipModel] = Field(default_factory=list)



class QueryRequest(BaseModel):
    """Fact Knowledge Layer natural language query."""
    query: str = Field(..., description="Factual question or conflict inquiry.", examples=["What was Delhivery's revenue in FY2024?"])
    document_ids: Optional[List[str]] = Field(None, description="Optional document ID filter scope.", examples=[["doc_a", "doc_b"]])


class QueryResponse(BaseModel):
    """Structured response to a Knowledge Layer query."""
    query: str = Field(..., examples=["What was Delhivery's revenue in FY2024?"])
    status: str = Field(..., description="'answered' | 'contradiction_found' | 'no_results' | 'ambiguous'", examples=["contradiction_found"])
    facts: List[FactModel] = Field(default_factory=list)
    relationships: List[RelationshipModel] = Field(default_factory=list)


class ErrorDetail(BaseModel):
    """Standardized error details."""
    code: str = Field(..., examples=["DOCUMENT_NOT_FOUND"])
    message: str = Field(..., examples=["Document 'doc_123' was not found."])
    details: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Consistent API error response envelope."""
    error: ErrorDetail
