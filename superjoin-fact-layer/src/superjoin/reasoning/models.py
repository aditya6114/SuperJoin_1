from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid

from superjoin.extraction.models import Fact


class RelationshipType(str, Enum):
    """Semantic relationship between two facts."""
    CORROBORATES = "CORROBORATES"
    CONTRADICTS = "CONTRADICTS"
    CONTEXTUALLY_RECONCILED = "CONTEXTUALLY_RECONCILED"
    UNRELATED = "UNRELATED"
    UNRESOLVED = "UNRESOLVED"


class ComparisonSignals(BaseModel):
    """Comparison signals across individual factual dimensions."""
    subject: str = Field(..., description="Subject comparison: 'exact', 'alias', 'different', 'unknown'")
    predicate: str = Field(..., description="Predicate comparison: 'exact', 'compatible', 'different', 'unknown'")
    fact_type: str = Field(..., description="Fact type comparison: 'compatible', 'incompatible'")
    value: str = Field(..., description="Value comparison: 'equal', 'equivalent', 'different', 'compatible', 'unknown', 'not_applicable'")
    unit: str = Field(..., description="Unit comparison: 'same', 'converted', 'different', 'missing', 'not_applicable'")
    time: str = Field(..., description="Time comparison: 'same', 'different', 'overlapping', 'contained', 'unknown'")
    scope: str = Field(..., description="Scope comparison: 'same', 'different', 'unknown'")
    qualifiers: str = Field(..., description="Qualifiers comparison: 'exact', 'compatible', 'different', 'missing'")
    status: Optional[str] = Field(None, description="Contextual or semantic status (e.g. 'status_transition', 'same_state')")


class ProvenanceEvidence(BaseModel):
    """Evidence citations preserved from source CanonicalElements."""
    fact_a_evidence: List[str] = Field(default_factory=list, description="IDs of CanonicalElements supporting Fact A")
    fact_b_evidence: List[str] = Field(default_factory=list, description="IDs of CanonicalElements supporting Fact B")


class RelationshipResult(BaseModel):
    """The complete result of reasoning about the semantic relationship between two facts."""
    relationship_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique identifier for this relationship result")
    fact_a_id: str
    fact_b_id: str
    document_a_id: Optional[str] = None
    document_b_id: Optional[str] = None
    relationship: RelationshipType
    confidence: float = Field(ge=0.0, le=1.0, description="Deterministic confidence score between 0.0 and 1.0")
    reason: str = Field(..., description="Concise deterministic summary reason")
    explanation: str = Field(..., description="Detailed, explainable description grounded in structured signals")
    comparison: ComparisonSignals
    evidence: ProvenanceEvidence
    source_independence: str = Field(
        default="cross_document",
        description="Indicates whether facts originate from 'cross_document' or 'same_document'"
    )
    fact_a: Optional[Fact] = Field(None, description="Full copy of Fact A preserving complete provenance")
    fact_b: Optional[Fact] = Field(None, description="Full copy of Fact B preserving complete provenance")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RelationshipStatistics(BaseModel):
    """Metrics regarding relationship reasoning execution."""
    total_pairs: int = 0
    corroborates: int = 0
    contradicts: int = 0
    contextually_reconciled: int = 0
    unrelated: int = 0
    unresolved: int = 0
    cross_document_count: int = 0
    same_document_count: int = 0
    average_confidence: float = 0.0
    execution_time_ms: float = 0.0


class RelationshipSessionResult(BaseModel):
    """Complete collection of relationship reasoning results and session statistics."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    relationships: List[RelationshipResult] = Field(default_factory=list)
    statistics: RelationshipStatistics = Field(default_factory=RelationshipStatistics)
    metadata: Dict[str, Any] = Field(default_factory=dict)
