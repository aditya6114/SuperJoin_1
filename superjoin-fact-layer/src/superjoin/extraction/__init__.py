"""
Superjoin Fact Extraction Layer (Module 2)

Extracts atomic, structured facts with complete evidence provenance from CanonicalDocument.
"""

from .models import (
    Fact,
    Subject,
    FactValue,
    TimeContext,
    FactList,
    ExtractionCandidate,
    ExtractionFailure,
    ExtractionStatistics,
    FactExtractionResult
)
from .candidate_selector import select_candidates
from .context_builder import build_context
from .validators import validate_fact, validate_facts
from .deduplicator import deduplicate_facts
from .service import FactExtractionService
from .llm.client import LLMClient
from .llm.provider import DefaultLLMProvider, MockLLMProvider

__all__ = [
    "Fact",
    "Subject",
    "FactValue",
    "TimeContext",
    "FactList",
    "ExtractionCandidate",
    "ExtractionFailure",
    "ExtractionStatistics",
    "FactExtractionResult",
    "select_candidates",
    "build_context",
    "validate_fact",
    "validate_facts",
    "deduplicate_facts",
    "FactExtractionService",
    "LLMClient",
    "DefaultLLMProvider",
    "MockLLMProvider"
]
