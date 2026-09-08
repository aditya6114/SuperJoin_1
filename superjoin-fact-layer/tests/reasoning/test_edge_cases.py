import pytest
from superjoin.extraction.models import Fact, FactSubject, FactObject, TemporalContext
from superjoin.matching.deterministic_matcher import DeterministicMatcher
from superjoin.matching.models import CandidatePair
from superjoin.reasoning.service import RelationshipReasoningService
from superjoin.reasoning.models import RelationshipType


@pytest.fixture
def matcher():
    return DeterministicMatcher()


@pytest.fixture
def service():
    return RelationshipReasoningService()


def test_bounded_lower_bound_corroboration(matcher, service):
    """Lower bound 'over 1,607' vs 2,000 centres in FY2024 -> CORROBORATES."""
    fact_bound = Fact(
        fact_id="b-1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="centres",
        object=FactObject(value_type="quantity", value=1607, qualifier="greater_than"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e1"]
    )
    fact_actual = Fact(
        fact_id="b-2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="centres",
        object=FactObject(value_type="quantity", value=2000),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e2"]
    )
    cand = CandidatePair(fact_a_id="b-1", fact_b_id="b-2", document_a_id="d1", document_b_id="d2")
    match = matcher.compare(fact_bound, fact_actual, candidate=cand)
    rel = service.reason_match(match)

    assert rel.relationship == RelationshipType.CORROBORATES
    assert "bounds" in rel.reason or "approximation" in rel.reason


def test_bounded_lower_bound_contradiction(matcher, service):
    """Lower bound 'over 1,607' vs 1,200 centres in FY2024 -> CONTRADICTS."""
    fact_bound = Fact(
        fact_id="b-1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="centres",
        object=FactObject(value_type="quantity", value=1607, qualifier="greater_than"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e1"]
    )
    fact_violat = Fact(
        fact_id="b-3",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="centres",
        object=FactObject(value_type="quantity", value=1200),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e3"]
    )
    cand = CandidatePair(fact_a_id="b-1", fact_b_id="b-3", document_a_id="d1", document_b_id="d2")
    match = matcher.compare(fact_bound, fact_violat, candidate=cand)
    rel = service.reason_match(match)

    assert rel.relationship == RelationshipType.CONTRADICTS
    assert "materially different values" in rel.reason


def test_percentage_and_decimal_corroboration(matcher, service):
    """5% vs 0.05 in FY2024 -> CORROBORATES."""
    fact_pct = Fact(
        fact_id="p-1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="market_share",
        object=FactObject(value_type="percentage", value=5, unit="%"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e1"]
    )
    fact_dec = Fact(
        fact_id="p-2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="market_share",
        object=FactObject(value_type="number", value=0.05),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e2"]
    )
    cand = CandidatePair(fact_a_id="p-1", fact_b_id="p-2", document_a_id="d1", document_b_id="d2")
    match = matcher.compare(fact_pct, fact_dec, candidate=cand)
    rel = service.reason_match(match)

    assert rel.relationship == RelationshipType.CORROBORATES


def test_internal_document_contradiction(matcher, service):
    """Same document contradiction: ₹500 Cr vs ₹600 Cr in FY2024.
    Should be CONTRADICTS with source_independence='same_document'.
    """
    fact_a = Fact(
        fact_id="intra-1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["p1:b1"]
    )
    fact_b = Fact(
        fact_id="intra-2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=600, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["p15:b20"]
    )
    cand = CandidatePair(fact_a_id="intra-1", fact_b_id="intra-2", document_a_id="doc-intra", document_b_id="doc-intra")
    match = matcher.compare(fact_a, fact_b, candidate=cand)
    rel = service.reason_match(match)

    assert rel.relationship == RelationshipType.CONTRADICTS
    assert rel.source_independence == "same_document"
