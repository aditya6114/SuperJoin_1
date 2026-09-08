import pytest
from superjoin.extraction.models import Fact, FactSubject, FactObject, TemporalContext
from superjoin.reasoning.models import (
    RelationshipType,
    ComparisonSignals,
    ProvenanceEvidence,
    RelationshipResult,
    RelationshipStatistics,
    RelationshipSessionResult,
)


def test_relationship_models_instantiation_and_serialization():
    signals = ComparisonSignals(
        subject="exact",
        predicate="exact",
        fact_type="compatible",
        value="equivalent",
        unit="converted",
        time="same",
        scope="same",
        qualifiers="exact",
        status=None,
    )
    evidence = ProvenanceEvidence(
        fact_a_evidence=["doc1:p1:b1"],
        fact_b_evidence=["doc2:p3:b5"],
    )
    result = RelationshipResult(
        fact_a_id="fa-1",
        fact_b_id="fb-2",
        document_a_id="doc1",
        document_b_id="doc2",
        relationship=RelationshipType.CORROBORATES,
        confidence=0.96,
        reason="Equivalent numerical value across converted units.",
        explanation="Both facts state Delhivery revenue for FY2024 is ₹5 crore / ₹50 million.",
        comparison=signals,
        evidence=evidence,
        source_independence="cross_document",
    )

    assert result.relationship == RelationshipType.CORROBORATES
    assert result.confidence == 0.96
    assert result.source_independence == "cross_document"

    # Test serialization roundtrip
    dumped = result.model_dump(mode="json")
    loaded = RelationshipResult.model_validate(dumped)
    assert loaded.fact_a_id == "fa-1"
    assert loaded.relationship == RelationshipType.CORROBORATES
    assert loaded.comparison.value == "equivalent"
    assert loaded.evidence.fact_a_evidence == ["doc1:p1:b1"]


def test_session_statistics_and_result():
    stats = RelationshipStatistics(
        total_pairs=10,
        corroborates=4,
        contradicts=2,
        contextually_reconciled=3,
        unrelated=0,
        unresolved=1,
        cross_document_count=8,
        same_document_count=2,
        average_confidence=0.89,
        execution_time_ms=12.5,
    )
    session = RelationshipSessionResult(
        statistics=stats,
        relationships=[],
    )
    dumped = session.model_dump(mode="json")
    assert dumped["statistics"]["corroborates"] == 4
    assert dumped["statistics"]["cross_document_count"] == 8
