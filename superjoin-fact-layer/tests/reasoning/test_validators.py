import pytest
from superjoin.reasoning.models import (
    RelationshipResult,
    RelationshipType,
    ComparisonSignals,
    ProvenanceEvidence,
)
from superjoin.reasoning.validators import validate_relationship_result, RelationshipValidationError
from superjoin.extraction.models import Fact, FactSubject, FactObject


def test_validator_detects_self_comparison():
    signals = ComparisonSignals(
        subject="exact", predicate="exact", fact_type="compatible",
        value="equal", unit="same", time="same", scope="same", qualifiers="exact"
    )
    result = RelationshipResult(
        fact_a_id="f1",
        fact_b_id="f1",
        relationship=RelationshipType.CORROBORATES,
        confidence=0.95,
        reason="Reason",
        explanation="Explanation",
        comparison=signals,
        evidence=ProvenanceEvidence(fact_a_evidence=["e1"], fact_b_evidence=["e1"]),
    )
    errors = validate_relationship_result(result)
    assert any("cannot compare a fact with itself" in e for e in errors)


def test_validator_detects_invalid_confidence():
    signals = ComparisonSignals(
        subject="exact", predicate="exact", fact_type="compatible",
        value="equal", unit="same", time="same", scope="same", qualifiers="exact"
    )
    # Pydantic may validate ge/le, but if bypassed or at edge
    with pytest.raises(Exception):
        RelationshipResult(
            fact_a_id="f1",
            fact_b_id="f2",
            relationship=RelationshipType.CORROBORATES,
            confidence=1.5,
            reason="Reason",
            explanation="Explanation",
            comparison=signals,
            evidence=ProvenanceEvidence(),
        )


def test_validator_detects_fabricated_evidence():
    fact_a = Fact(
        fact_id="f1",
        fact_type="numerical",
        subject=FactSubject(name="Co", type="company"),
        predicate="rev",
        object=FactObject(value_type="number", value=100),
        confidence=0.9,
        evidence_ids=["real_ev_1"]
    )
    signals = ComparisonSignals(
        subject="exact", predicate="exact", fact_type="compatible",
        value="equal", unit="same", time="same", scope="same", qualifiers="exact"
    )
    result = RelationshipResult(
        fact_a_id="f1",
        fact_b_id="f2",
        relationship=RelationshipType.CORROBORATES,
        confidence=0.95,
        reason="Reason",
        explanation="Explanation",
        comparison=signals,
        evidence=ProvenanceEvidence(fact_a_evidence=["fabricated_ev_99"], fact_b_evidence=[]),
        fact_a=fact_a
    )
    errors = validate_relationship_result(result)
    assert any("fabricated_ev_99" in e for e in errors)


def test_validator_passes_valid_result():
    signals = ComparisonSignals(
        subject="exact", predicate="exact", fact_type="compatible",
        value="equal", unit="same", time="same", scope="same", qualifiers="exact"
    )
    result = RelationshipResult(
        fact_a_id="f1",
        fact_b_id="f2",
        relationship=RelationshipType.CORROBORATES,
        confidence=0.95,
        reason="Valid reason",
        explanation="Valid detailed explanation",
        comparison=signals,
        evidence=ProvenanceEvidence(fact_a_evidence=["e1"], fact_b_evidence=["e2"]),
    )
    errors = validate_relationship_result(result)
    assert len(errors) == 0
