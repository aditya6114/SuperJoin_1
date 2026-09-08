import pytest
from superjoin.extraction.models import Fact, FactSubject, FactObject, TemporalContext
from superjoin.matching.models import MatchResult, MatchSignals, MatchClassification
from superjoin.reasoning.compatibility import ComparisonContext
from superjoin.reasoning.contradiction import ContradictionEvaluator


@pytest.fixture
def evaluator():
    return ContradictionEvaluator()


def test_contradiction_same_period_different_values(evaluator):
    """₹500 Cr vs ₹600 Cr in FY2024 -> CONTRADICTS."""
    fact_a = Fact(
        fact_id="f1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e1"]
    )
    fact_b = Fact(
        fact_id="f2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=600, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e2"]
    )
    signals = MatchSignals(
        subject="exact",
        predicate="exact",
        fact_type="compatible",
        value="different",
        unit="same",
        time="same",
        scope="same",
        qualifiers="exact"
    )
    match = MatchResult(
        fact_a_id="f1",
        fact_b_id="f2",
        document_a_id="doc1",
        document_b_id="doc2",
        classification=MatchClassification.SAME_CLAIM,
        confidence=0.90,
        signals=signals,
        reasons=["Different values"],
        fact_a=fact_a,
        fact_b=fact_b
    )
    ctx = ComparisonContext(match)
    result = evaluator.evaluate(ctx)
    assert result is not None
    conf, reason, explanation = result
    assert conf >= 0.85
    assert "materially different values" in reason
    assert "mutually incompatible" in explanation


def test_contradiction_percentage_disagreement(evaluator):
    """5% vs 8% market share in FY2024 -> CONTRADICTS."""
    fact_a = Fact(
        fact_id="f1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="market_share",
        object=FactObject(value_type="percentage", value=5, unit="%"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e1"]
    )
    fact_b = Fact(
        fact_id="f2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="market_share",
        object=FactObject(value_type="percentage", value=8, unit="%"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e2"]
    )
    signals = MatchSignals(
        subject="exact",
        predicate="exact",
        fact_type="compatible",
        value="different",
        unit="same",
        time="same",
        scope="same",
        qualifiers="exact"
    )
    match = MatchResult(
        fact_a_id="f1",
        fact_b_id="f2",
        document_a_id="doc1",
        document_b_id="doc2",
        classification=MatchClassification.SAME_CLAIM,
        confidence=0.90,
        signals=signals,
        reasons=["Different percentage"],
        fact_a=fact_a,
        fact_b=fact_b
    )
    ctx = ComparisonContext(match)
    result = evaluator.evaluate(ctx)
    assert result is not None
    conf, reason, explanation = result
    assert "materially different values" in reason


def test_no_contradiction_when_time_differs(evaluator):
    """₹500 Cr vs ₹600 Cr with different years -> NOT a contradiction."""
    fact_a = Fact(
        fact_id="f1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2023"),
        confidence=0.95,
        evidence_ids=["e1"]
    )
    fact_b = Fact(
        fact_id="f2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=600, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e2"]
    )
    signals = MatchSignals(
        subject="exact",
        predicate="exact",
        fact_type="compatible",
        value="different",
        unit="same",
        time="different",
        scope="same",
        qualifiers="exact"
    )
    match = MatchResult(
        fact_a_id="f1",
        fact_b_id="f2",
        document_a_id="doc1",
        document_b_id="doc2",
        classification=MatchClassification.RELATED_CLAIM,
        confidence=0.88,
        signals=signals,
        reasons=["Different times"],
        fact_a=fact_a,
        fact_b=fact_b
    )
    ctx = ComparisonContext(match)
    assert evaluator.evaluate(ctx) is None


def test_no_contradiction_when_time_is_unknown(evaluator):
    """₹500 Cr vs ₹600 Cr with time=unknown -> Refuse false contradiction (must be None)."""
    fact_a = Fact(
        fact_id="f1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="unknown"),
        confidence=0.95,
        evidence_ids=["e1"]
    )
    fact_b = Fact(
        fact_id="f2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=600, currency="₹", scale="crore"),
        time=TemporalContext(time_type="unknown"),
        confidence=0.95,
        evidence_ids=["e2"]
    )
    signals = MatchSignals(
        subject="exact",
        predicate="exact",
        fact_type="compatible",
        value="different",
        unit="same",
        time="unknown",
        scope="same",
        qualifiers="exact"
    )
    match = MatchResult(
        fact_a_id="f1",
        fact_b_id="f2",
        document_a_id="doc1",
        document_b_id="doc2",
        classification=MatchClassification.SAME_CLAIM,
        confidence=0.85,
        signals=signals,
        reasons=["Unknown time"],
        fact_a=fact_a,
        fact_b=fact_b
    )
    ctx = ComparisonContext(match)
    assert evaluator.evaluate(ctx) is None
