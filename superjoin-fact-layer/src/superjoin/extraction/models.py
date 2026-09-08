from pydantic import BaseModel, Field
from typing import Optional, List, Any, Union, Literal, Dict
import uuid


class FactSubject(BaseModel):
    """Represents the entity a fact is about."""
    name: str = Field(..., description="The exact name of the entity as written in the source.")
    type: str = Field(..., description="The type of the entity (e.g., 'company', 'person', 'location', 'product', 'concept').")


# Backward compatibility alias
Subject = FactSubject


class TemporalContext(BaseModel):
    """Structured temporal representation."""
    time_type: Literal[
        "specific_date", 
        "date_range", 
        "calendar_year", 
        "fiscal_year", 
        "quarter", 
        "month", 
        "as_of_date", 
        "relative_time", 
        "unknown"
    ] = Field(default="unknown", description="The category of the time expression.")
    value: Optional[str] = Field(None, description="The original time expression from the text (e.g., 'FY2022', 'December 31, 2021').")
    start_date: Optional[str] = Field(None, description="ISO-formatted start date if explicitly specified.")
    end_date: Optional[str] = Field(None, description="ISO-formatted end date if explicitly specified.")


# Backward compatibility alias
TimeContext = TemporalContext


class FactObject(BaseModel):
    """Represents the object or value of the fact."""
    value_type: Literal["number", "percentage", "currency", "quantity", "text", "entity", "boolean", "date"] = Field(
        description="The type of the extracted value."
    )
    value: Any = Field(..., description="The exact extracted value.")
    unit: Optional[str] = Field(None, description="The original unit (e.g., 'square feet', 'million tonnes', 'centres').")
    currency: Optional[str] = Field(None, description="The currency (e.g., '₹', 'INR', 'USD', '$').")
    scale: Optional[str] = Field(None, description="The scale of the number (e.g., 'million', 'crore', 'billion', 'lakh').")
    qualifier: Optional[str] = Field(None, description="Value-level qualifier (e.g., 'greater_than', 'less_than', 'approximate').")


# Backward compatibility alias
FactValue = FactObject


class Fact(BaseModel):
    """An atomic, meaningful claim explicitly supported by document evidence."""
    fact_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique identifier for the fact.")
    fact_type: Literal["numerical", "semantic", "event", "attribute", "relationship"] = Field(
        description="The type of claim."
    )
    subject: FactSubject
    predicate: str = Field(..., description="The property or relationship (e.g., 'revenue', 'operates', 'acquired').")
    object: FactObject
    time: TemporalContext = Field(default_factory=lambda: TemporalContext(time_type="unknown"))
    scope: Optional[str] = Field(None, description="The context, like geography or business unit (e.g., 'India', 'consolidated operations').")
    qualifiers: List[str] = Field(default_factory=list, description="Semantic qualifiers (e.g., 'approximately', 'over', 'unaudited').")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence that the fact accurately represents the evidence (0 to 1).")
    evidence_ids: List[str] = Field(..., min_length=1, description="IDs of CanonicalElements that support this claim.")


class FactList(BaseModel):
    """Container for multiple extracted facts from an LLM call or candidate block."""
    facts: List[Fact] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list, description="Notes on ambiguous or ungrounded statements encountered.")


class ExtractionCandidate(BaseModel):
    """Wrapper around a document element selected for extraction."""
    element_id: str
    element_type: str
    canonical_order: int
    priority: int
    page_number: int
    printed_page_number: Optional[int] = None
    content_preview: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExtractionFailure(BaseModel):
    """Record of a failed candidate extraction or validation."""
    document_id: str
    page_number: int
    candidate_id: str
    element_id: str
    reason: str
    details: Optional[Dict[str, Any]] = None


# Backward compatibility alias
ExtractionIssue = ExtractionFailure


class ExtractionStatistics(BaseModel):
    """Metrics regarding the extraction pipeline run."""
    candidate_count: int = 0
    text_candidate_count: int = 0
    table_candidate_count: int = 0
    figure_candidate_count: int = 0
    facts_extracted: int = 0
    facts_rejected: int = 0
    facts_uncertain: int = 0
    validation_failures: int = 0


class FactExtractionResult(BaseModel):
    """The complete result of extracting facts from a CanonicalDocument."""
    document_id: str
    facts: List[Fact] = Field(default_factory=list)
    uncertain_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    failed_candidates: List[ExtractionFailure] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    statistics: ExtractionStatistics = Field(default_factory=ExtractionStatistics)


# Backward compatibility alias
ExtractionResult = FactExtractionResult
