"""
Superjoin Fact Extraction Layer (Module 2)

Extracts atomic, structured, evidence-grounded facts with complete
provenance tracking from CanonicalDocument.
"""

from .models import (
    Fact,
    FactSubject,
    FactObject,
    TemporalContext,
    Subject,
    FactValue,
    TimeContext,
    FactList,
    ExtractionCandidate,
    ExtractionFailure,
    ExtractionIssue,
    ExtractionStatistics,
    FactExtractionResult,
    ExtractionResult,
)
from .candidate_selector import select_candidates
from .context_builder import build_context, build_context_dict
from .validators import validate_fact, validate_facts
from .deduplicator import deduplicate_facts
from .fact_builder import build_fact
from .service import FactExtractionService
from .llm.client import LLMClient, MockLLMClient, OpenAILLMClient

__all__ = [
    "Fact",
    "FactSubject",
    "FactObject",
    "TemporalContext",
    "Subject",
    "FactValue",
    "TimeContext",
    "FactList",
    "ExtractionCandidate",
    "ExtractionFailure",
    "ExtractionIssue",
    "ExtractionStatistics",
    "FactExtractionResult",
    "ExtractionResult",
    "select_candidates",
    "build_context",
    "build_context_dict",
    "validate_fact",
    "validate_facts",
    "deduplicate_facts",
    "build_fact",
    "FactExtractionService",
    "LLMClient",
    "MockLLMClient",
    "OpenAILLMClient",
]
