import pytest
from superjoin.extraction.models import Fact, FactSubject, FactObject, TemporalContext
from superjoin.matching.models import MatchResult, MatchSignals, MatchClassification
from superjoin.reasoning.compatibility import ComparisonContext, normalize_key, format_fact_value, format_fact_time


@pytest.fixture
def sample_match():
    fact_a = Fact(
        fact_id="doc1:f1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        scope="consolidated",
        confidence=0.95,
        evidence_ids=["e1"]
    )
    fact_b = Fact(
        fact_id="doc2:f2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery Limited", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        scope="consolidated",
        confidence=0.95,
        evidence_ids=["e2"]
    )
    signals = MatchSignals(
        subject="alias",
        predicate="exact",
        fact_type="compatible",
        value="equal",
        unit="same",
        time="same",
        scope="same",
        qualifiers="exact"
    )
    return MatchResult(
        fact_a_id=fact_a.fact_id,
        fact_b_id=fact_b.fact_b_id if hasattr(fact_b, 'fact_b_id') else fact_b.fact_id,
        document_a_id="doc1",
        document_b_id="doc2",
        classification=MatchClassification.SAME_CLAIM,
        confidence=0.95,
        signals=signals,
        reasons=["Same claim"],
        fact_a=fact_a,
        fact_b=fact_b
    )


def test_comparison_context_properties(sample_match):
    ctx = ComparisonContext(sample_match)
    assert ctx.is_same_entity is True
    assert ctx.is_same_predicate is True
    assert ctx.is_status_transition is False
    assert ctx.is_compatible_fact_type is True
    assert ctx.is_same_time is True
    assert ctx.is_same_scope is True
    assert ctx.is_value_agreeing is True
    assert ctx.is_value_different is False
    assert ctx.source_independence == "cross_document"


def test_status_transition_detection():
    fact_a = Fact(
        fact_id="doc1:f1",
        fact_type="event",
        subject=FactSubject(name="Alice", type="person"),
        predicate="appointed_ceo",
        object=FactObject(value_type="text", value="CEO"),
        time=TemporalContext(time_type="calendar_year", value="2021"),
        confidence=0.9,
        evidence_ids=["e1"]
    )
    fact_b = Fact(
        fact_id="doc2:f2",
        fact_type="event",
        subject=FactSubject(name="Alice", type="person"),
        predicate="resigned_ceo",
        object=FactObject(value_type="text", value="CEO"),
        time=TemporalContext(time_type="calendar_year", value="2024"),
        confidence=0.9,
        evidence_ids=["e2"]
    )
    signals = MatchSignals(
        subject="exact",
        predicate="compatible",
        fact_type="compatible",
        value="equal",
        unit="not_applicable",
        time="different",
        scope="same",
        qualifiers="exact"
    )
    match = MatchResult(
        fact_a_id="doc1:f1",
        fact_b_id="doc2:f2",
        document_a_id="doc1",
        document_b_id="doc2",
        classification=MatchClassification.RELATED_CLAIM,
        confidence=0.85,
        signals=signals,
        reasons=["Status transition"],
        fact_a=fact_a,
        fact_b=fact_b
    )
    ctx = ComparisonContext(match)
    assert ctx.is_status_transition is True
    assert ctx.status == "status_transition"
    assert ctx.is_different_time is True


def test_format_helpers():
    fact = Fact(
        fact_id="f1",
        fact_type="numerical",
        subject=FactSubject(name="Test", type="company"),
        predicate="metric",
        object=FactObject(value_type="currency", value=42, currency="$", unit="million", qualifier="approximate"),
        time=TemporalContext(time_type="fiscal_year", value="FY2025"),
        scope="India",
        confidence=0.9,
        evidence_ids=["e1"]
    )
    assert "approximate" in format_fact_value(fact)
    assert "$ 42" in format_fact_value(fact)
    assert format_fact_time(fact) == "FY2025"
