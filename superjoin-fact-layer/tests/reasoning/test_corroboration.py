import pytest
from superjoin.extraction.models import Fact, FactSubject, FactObject, TemporalContext
from superjoin.matching.models import MatchResult, MatchSignals, MatchClassification
from superjoin.reasoning.compatibility import ComparisonContext
from superjoin.reasoning.corroboration import CorroborationEvaluator


@pytest.fixture
def evaluator():
    return CorroborationEvaluator()


def test_corroborates_unit_conversion(evaluator):
    """₹5 crore vs ₹50 million in FY2024 -> CORROBORATES."""
    fact_a = Fact(
        fact_id="f1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=5, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e1"]
    )
    fact_b = Fact(
        fact_id="f2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=50, currency="₹", scale="million"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e2"]
    )
    signals = MatchSignals(
        subject="exact",
        predicate="exact",
        fact_type="compatible",
        value="equivalent",
        unit="converted",
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
        confidence=0.95,
        signals=signals,
        reasons=["Equivalent units"],
        fact_a=fact_a,
        fact_b=fact_b
    )
    ctx = ComparisonContext(match)
    result = evaluator.evaluate(ctx)
    assert result is not None
    conf, reason, explanation = result
    assert conf >= 0.90
    assert "numerically equivalent" in reason
    assert "Cross-document" in explanation


def test_corroborates_approximate_tolerance(evaluator):
    """approx 5.0M vs 5.02M employees -> CORROBORATES with approximation qualification."""
    fact_a = Fact(
        fact_id="f1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="employees",
        object=FactObject(value_type="quantity", value=5.0, scale="million", qualifier="approximate"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.92,
        evidence_ids=["e1"]
    )
    fact_b = Fact(
        fact_id="f2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="employees",
        object=FactObject(value_type="quantity", value=5.02, scale="million"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.94,
        evidence_ids=["e2"]
    )
    signals = MatchSignals(
        subject="exact",
        predicate="exact",
        fact_type="compatible",
        value="compatible",
        unit="same",
        time="same",
        scope="same",
        qualifiers="compatible"
    )
    match = MatchResult(
        fact_a_id="f1",
        fact_b_id="f2",
        document_a_id="doc1",
        document_b_id="doc2",
        classification=MatchClassification.SAME_CLAIM,
        confidence=0.90,
        signals=signals,
        reasons=["Compatible approx"],
        fact_a=fact_a,
        fact_b=fact_b
    )
    ctx = ComparisonContext(match)
    result = evaluator.evaluate(ctx)
    assert result is not None
    conf, reason, explanation = result
    assert "approximation tolerance" in reason


def test_no_corroboration_when_time_differs(evaluator):
    """Values equal but different years -> Should NOT corroborate."""
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
        object=FactObject(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e2"]
    )
    signals = MatchSignals(
        subject="exact",
        predicate="exact",
        fact_type="compatible",
        value="equal",
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
        reasons=["Different time"],
        fact_a=fact_a,
        fact_b=fact_b
    )
    ctx = ComparisonContext(match)
    assert evaluator.evaluate(ctx) is None


def test_same_document_corroboration(evaluator):
    """Breakpoint 12 — Same-document corroboration produces CORROBORATES with source_independence = same_document."""
    fact_a = Fact(
        fact_id="doc1:p5:f1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["doc1:ev1"]
    )
    fact_b = Fact(
        fact_id="doc1:p17:f2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["doc1:ev2"]
    )
    signals = MatchSignals(
        subject="exact",
        predicate="exact",
        fact_type="compatible",
        value="equal",
        unit="same",
        time="same",
        scope="same",
        qualifiers="exact"
    )
    match = MatchResult(
        fact_a_id="doc1:p5:f1",
        fact_b_id="doc1:p17:f2",
        document_a_id="doc1",
        document_b_id="doc1",
        classification=MatchClassification.SAME_CLAIM,
        confidence=0.95,
        signals=signals,
        reasons=["Equal value within document"],
        fact_a=fact_a,
        fact_b=fact_b
    )
    ctx = ComparisonContext(match)
    assert ctx.source_independence == "same_document"
    res = evaluator.evaluate(ctx)
    assert res is not None
    conf, reason, explanation = res
    assert "Internal corroboration confirmed within the same source document" in explanation


def test_cross_document_corroboration(evaluator):
    """Breakpoint 12 — Cross-document corroboration produces CORROBORATES with source_independence = cross_document."""
    fact_a = Fact(
        fact_id="doc1:f1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["doc1:ev1"]
    )
    fact_b = Fact(
        fact_id="doc2:f2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["doc2:ev2"]
    )
    signals = MatchSignals(
        subject="exact",
        predicate="exact",
        fact_type="compatible",
        value="equal",
        unit="same",
        time="same",
        scope="same",
        qualifiers="exact"
    )
    match = MatchResult(
        fact_a_id="doc1:f1",
        fact_b_id="doc2:f2",
        document_a_id="doc1",
        document_b_id="doc2",
        classification=MatchClassification.SAME_CLAIM,
        confidence=0.95,
        signals=signals,
        reasons=["Equal value across documents"],
        fact_a=fact_a,
        fact_b=fact_b
    )
    ctx = ComparisonContext(match)
    assert ctx.source_independence == "cross_document"
    res = evaluator.evaluate(ctx)
    assert res is not None
    conf, reason, explanation = res
    assert "Cross-document corroboration confirmed across independent sources" in explanation
