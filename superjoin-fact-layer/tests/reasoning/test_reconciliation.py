import pytest
from superjoin.extraction.models import Fact, FactSubject, FactObject, TemporalContext
from superjoin.matching.models import MatchResult, MatchSignals, MatchClassification
from superjoin.reasoning.compatibility import ComparisonContext
from superjoin.reasoning.reconciliation import ContextualReconciliationEvaluator


@pytest.fixture
def evaluator():
    return ContextualReconciliationEvaluator()


def test_reconciliation_different_year(evaluator):
    """₹500 Cr FY2023 vs ₹600 Cr FY2024 -> CONTEXTUALLY_RECONCILED."""
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
    result = evaluator.evaluate(ctx)
    assert result is not None
    conf, reason, explanation = result
    assert "different reporting periods" in reason
    assert "FY2023" in explanation
    assert "FY2024" in explanation


def test_reconciliation_different_scope(evaluator):
    """Consolidated ₹100 Cr vs India segment ₹30 Cr -> CONTEXTUALLY_RECONCILED."""
    fact_a = Fact(
        fact_id="f1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=100, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        scope="consolidated",
        confidence=0.95,
        evidence_ids=["e1"]
    )
    fact_b = Fact(
        fact_id="f2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=30, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        scope="India segment",
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
        scope="different",
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
        reasons=["Different scope"],
        fact_a=fact_a,
        fact_b=fact_b
    )
    ctx = ComparisonContext(match)
    result = evaluator.evaluate(ctx)
    assert result is not None
    conf, reason, explanation = result
    assert "different reporting scopes" in reason
    assert "consolidated" in explanation
    assert "India segment" in explanation


def test_reconciliation_status_transition(evaluator):
    """Alice appointed CEO 2021 vs Alice resigned CEO 2024 -> CONTEXTUALLY_RECONCILED."""
    fact_a = Fact(
        fact_id="f1",
        fact_type="event",
        subject=FactSubject(name="Alice", type="person"),
        predicate="appointed",
        object=FactObject(value_type="text", value="CEO"),
        time=TemporalContext(time_type="calendar_year", value="2021"),
        confidence=0.9,
        evidence_ids=["e1"]
    )
    fact_b = Fact(
        fact_id="f2",
        fact_type="event",
        subject=FactSubject(name="Alice", type="person"),
        predicate="resigned",
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
        fact_a_id="f1",
        fact_b_id="f2",
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
    result = evaluator.evaluate(ctx)
    assert result is not None
    conf, reason, explanation = result
    assert "status transition" in reason
    assert "appointed" in explanation
    assert "resigned" in explanation


def test_reconciliation_overlapping_contained_period(evaluator):
    """Q4 vs FY24 -> CONTEXTUALLY_RECONCILED."""
    fact_a = Fact(
        fact_id="f1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=2000, currency="₹", scale="crore"),
        time=TemporalContext(time_type="quarter", value="Q4 FY24"),
        confidence=0.95,
        evidence_ids=["e1"]
    )
    fact_b = Fact(
        fact_id="f2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=8000, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY24"),
        confidence=0.95,
        evidence_ids=["e2"]
    )
    signals = MatchSignals(
        subject="exact",
        predicate="exact",
        fact_type="compatible",
        value="different",
        unit="same",
        time="contained",
        scope="same",
        qualifiers="exact"
    )
    match = MatchResult(
        fact_a_id="f1",
        fact_b_id="f2",
        document_a_id="doc1",
        document_b_id="doc2",
        classification=MatchClassification.RELATED_CLAIM,
        confidence=0.85,
        signals=signals,
        reasons=["Contained time"],
        fact_a=fact_a,
        fact_b=fact_b
    )
    ctx = ComparisonContext(match)
    result = evaluator.evaluate(ctx)
    assert result is not None
    conf, reason, explanation = result
    assert "differing reporting durations" in reason
