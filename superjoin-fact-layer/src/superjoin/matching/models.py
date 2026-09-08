from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid

from superjoin.extraction.models import Fact


class MatchClassification(str, Enum):
    """Classification of the factual relationship between two facts."""
    SAME_CLAIM = "SAME_CLAIM"
    RELATED_CLAIM = "RELATED_CLAIM"
    NOT_MATCH = "NOT_MATCH"
    UNCERTAIN = "UNCERTAIN"


class CandidatePair(BaseModel):
    """Pair of facts nominated for comparison with initial retrieval signals."""
    fact_a_id: str
    fact_b_id: str
    document_a_id: Optional[str] = None
    document_b_id: Optional[str] = None
    signals: Dict[str, str] = Field(
        default_factory=dict,
        description="Retrieval blocking signals (e.g. {'subject': 'exact', 'predicate': 'exact'})."
    )


class MatchSignals(BaseModel):
    """Fine-grained comparison signals across individual factual dimensions."""
    subject: str = Field(
        ...,
        description="Subject signal: 'exact', 'alias', 'different', 'unknown'"
    )
    predicate: str = Field(
        ...,
        description="Predicate signal: 'exact', 'compatible', 'different', 'unknown'"
    )
    fact_type: str = Field(
        ...,
        description="Fact type signal: 'compatible', 'incompatible'"
    )
    value: str = Field(
        ...,
        description="Value signal: 'equal', 'equivalent', 'different', 'compatible', 'unknown', 'not_applicable'"
    )
    unit: str = Field(
        ...,
        description="Unit signal: 'same', 'converted', 'different', 'missing', 'not_applicable'"
    )
    time: str = Field(
        ...,
        description="Time signal: 'same', 'different', 'overlapping', 'contained', 'unknown'"
    )
    scope: str = Field(
        ...,
        description="Scope signal: 'same', 'different', 'unknown'"
    )
    qualifiers: str = Field(
        ...,
        description="Qualifiers signal: 'exact', 'compatible', 'different', 'missing'"
    )


class MatchResult(BaseModel):
    """The complete result of comparing two facts."""
    match_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    fact_a_id: str
    fact_b_id: str
    document_a_id: Optional[str] = None
    document_b_id: Optional[str] = None
    classification: MatchClassification
    confidence: float = Field(ge=0.0, le=1.0, description="Deterministic confidence score.")
    signals: MatchSignals
    reasons: List[str] = Field(default_factory=list, description="Human-readable deterministic explanations.")
    fact_a: Optional[Fact] = Field(None, description="Full copy of Fact A preserving provenance for Module 5.")
    fact_b: Optional[Fact] = Field(None, description="Full copy of Fact B preserving provenance for Module 5.")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MatchingStatistics(BaseModel):
    """Metrics regarding fact matching execution."""
    total_documents: int = 0
    total_facts: int = 0
    candidate_pairs: int = 0
    same_claim_count: int = 0
    related_claim_count: int = 0
    not_match_count: int = 0
    uncertain_count: int = 0
    execution_time_ms: float = 0.0


class MatchingSessionResult(BaseModel):
    """Complete collection of matches and metadata across processed documents."""
    matches: List[MatchResult] = Field(default_factory=list)
    statistics: MatchingStatistics = Field(default_factory=MatchingStatistics)
