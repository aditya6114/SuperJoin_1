import pytest
from superjoin.extraction.models import Fact, Subject, FactValue, TemporalContext
from superjoin.matching.models import MatchClassification
from superjoin.matching.deterministic_matcher import DeterministicMatcher


@pytest.fixture
def matcher():
    return DeterministicMatcher()


def test_case_a_same_claim_different_units(matcher):
    """Case A — Same claim, different units: ₹5 crore vs ₹50 million in FY2024."""
    fact_a = Fact(
        fact_id="case-a-doc1",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=5, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["ev-a"]
    )
    fact_b = Fact(
        fact_id="case-a-doc2",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=50, currency="₹", scale="million"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["ev-b"]
    )

    result = matcher.compare(fact_a, fact_b)
    assert result.classification == MatchClassification.SAME_CLAIM
    assert result.signals.value == "equivalent"
    assert result.signals.time == "same"
    assert result.signals.subject == "exact"
    assert result.signals.predicate == "exact"


def test_case_b_same_metric_different_time(matcher):
    """Case B — Same metric, different time: ₹500 crore in FY2023 vs ₹600 crore in FY2024."""
    fact_a = Fact(
        fact_id="case-b-doc1",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2023"),
        confidence=0.95,
        evidence_ids=["ev-a"]
    )
    fact_b = Fact(
        fact_id="case-b-doc2",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=600, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["ev-b"]
    )

    result = matcher.compare(fact_a, fact_b)
    assert result.classification == MatchClassification.RELATED_CLAIM
    assert result.signals.time == "different"
    assert result.signals.subject == "exact"
    assert result.signals.predicate == "exact"


def test_case_c_genuine_contradiction_candidate(matcher):
    """Case C — Genuine contradiction candidate: Revenue ₹500 crore vs ₹600 crore in FY2024.
    Must be SAME_CLAIM with value=different so Module 5 can decide contradiction.
    """
    fact_a = Fact(
        fact_id="case-c-doc1",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["ev-a"]
    )
    fact_b = Fact(
        fact_id="case-c-doc2",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=600, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["ev-b"]
    )

    result = matcher.compare(fact_a, fact_b)
    assert result.classification == MatchClassification.SAME_CLAIM
    assert result.signals.value == "different"
    assert result.signals.time == "same"
    assert result.signals.subject == "exact"
    assert result.signals.predicate == "exact"


def test_case_d_different_scope(matcher):
    """Case D — Different scope: Consolidated ₹100 crore vs India segment ₹30 crore."""
    fact_a = Fact(
        fact_id="case-d-doc1",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=100, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        scope="consolidated",
        confidence=0.95,
        evidence_ids=["ev-a"]
    )
    fact_b = Fact(
        fact_id="case-d-doc2",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=30, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        scope="India segment",
        confidence=0.95,
        evidence_ids=["ev-b"]
    )

    result = matcher.compare(fact_a, fact_b)
    assert result.classification == MatchClassification.RELATED_CLAIM
    assert result.signals.scope == "different"


def test_case_e_status_change(matcher):
    """Case E — Status change: Alice appointed CEO 2021 vs Alice resigned CEO 2024."""
    fact_a = Fact(
        fact_id="case-e-doc1",
        fact_type="event",
        subject=Subject(name="Alice", type="person"),
        predicate="appointed",
        object=FactValue(value_type="text", value="CEO"),
        time=TemporalContext(time_type="calendar_year", value="2021"),
        confidence=0.90,
        evidence_ids=["ev-a"]
    )
    fact_b = Fact(
        fact_id="case-e-doc2",
        fact_type="event",
        subject=Subject(name="Alice", type="person"),
        predicate="resigned",
        object=FactValue(value_type="text", value="CEO"),
        time=TemporalContext(time_type="calendar_year", value="2024"),
        confidence=0.90,
        evidence_ids=["ev-b"]
    )

    result = matcher.compare(fact_a, fact_b)
    assert result.classification == MatchClassification.RELATED_CLAIM


def test_case_f_different_entities(matcher):
    """Case F — Different entities: Delhivery revenue ₹500 crore vs Amazon revenue ₹600 crore."""
    fact_a = Fact(
        fact_id="case-f-doc1",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["ev-a"]
    )
    fact_b = Fact(
        fact_id="case-f-doc2",
        fact_type="numerical",
        subject=Subject(name="Amazon", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=600, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["ev-b"]
    )

    result = matcher.compare(fact_a, fact_b)
    assert result.classification == MatchClassification.NOT_MATCH
    assert result.signals.subject == "different"


def test_case_g_approximate_values(matcher):
    """Case G — Approximate values: approximately 5 million vs 5.02 million employees.
    Value must be compatible, NOT blind exact equality.
    """
    fact_a = Fact(
        fact_id="case-g-doc1",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="employee_count",
        object=FactValue(value_type="quantity", value=5.0, scale="million", qualifier="approximate"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["ev-a"]
    )
    fact_b = Fact(
        fact_id="case-g-doc2",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="employee_count",
        object=FactValue(value_type="quantity", value=5.02, scale="million"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["ev-b"]
    )

    result = matcher.compare(fact_a, fact_b)
    assert result.classification in {MatchClassification.SAME_CLAIM, MatchClassification.RELATED_CLAIM}
    assert result.signals.value == "compatible"
    assert result.signals.value != "equal"


def test_case_h_unknown_subject(matcher):
    """Case H — Unknown subject: 'It operates 50 facilities' vs 'Company X operates 60 facilities'.
    Expected: UNCERTAIN.
    """
    fact_a = Fact(
        fact_id="case-h-doc1",
        fact_type="numerical",
        subject=Subject(name="It", type="company"),
        predicate="operates",
        object=FactValue(value_type="quantity", value=50, unit="facilities"),
        time=TemporalContext(time_type="unknown"),
        confidence=0.85,
        evidence_ids=["ev-a"]
    )
    fact_b = Fact(
        fact_id="case-h-doc2",
        fact_type="numerical",
        subject=Subject(name="Company X", type="company"),
        predicate="operates",
        object=FactValue(value_type="quantity", value=60, unit="facilities"),
        time=TemporalContext(time_type="unknown"),
        confidence=0.90,
        evidence_ids=["ev-b"]
    )

    result = matcher.compare(fact_a, fact_b)
    assert result.classification == MatchClassification.UNCERTAIN
    assert result.signals.subject == "unknown"


def test_bounded_values_lower_bound(matcher):
    """Lower bound 'over 1,607' vs 2,000 (compatible) and 1,200 (different)."""
    fact_bound = Fact(
        fact_id="bound-1",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="centres",
        object=FactValue(value_type="quantity", value=1607, qualifier="greater_than"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e1"]
    )
    fact_compat = Fact(
        fact_id="compat-1",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="centres",
        object=FactValue(value_type="quantity", value=2000),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e2"]
    )
    fact_violat = Fact(
        fact_id="violat-1",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="centres",
        object=FactValue(value_type="quantity", value=1200),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e3"]
    )

    res_compat = matcher.compare(fact_bound, fact_compat)
    assert res_compat.signals.value == "compatible"
    assert res_compat.classification == MatchClassification.SAME_CLAIM

    res_violat = matcher.compare(fact_bound, fact_violat)
    assert res_violat.signals.value == "different"


def test_percentage_vs_decimal(matcher):
    """5% vs 0.05 equivalent."""
    fact_pct = Fact(
        fact_id="pct-1",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="market_share",
        object=FactValue(value_type="percentage", value=5),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e1"]
    )
    fact_dec = Fact(
        fact_id="dec-1",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="market_share",
        object=FactValue(value_type="number", value=0.05),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e2"]
    )

    res = matcher.compare(fact_pct, fact_dec)
    assert res.classification == MatchClassification.SAME_CLAIM
    assert res.signals.value == "equivalent"


def test_internal_document_disagreement(matcher):
    """Test intra-document comparison with generic subject ('Company') and differing values."""
    from superjoin.matching.models import CandidatePair

    fact_a = Fact(
        fact_id="intra-1",
        fact_type="numerical",
        subject=Subject(name="Company", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=100, currency="₹", scale="crore"),
        time=TemporalContext(time_type="unknown"),
        confidence=0.95,
        evidence_ids=["e1"]
    )
    fact_b = Fact(
        fact_id="intra-2",
        fact_type="numerical",
        subject=Subject(name="Company", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=120, currency="₹", scale="crore"),
        time=TemporalContext(time_type="unknown"),
        confidence=0.95,
        evidence_ids=["e2"]
    )

    cand = CandidatePair(
        fact_a_id="intra-1",
        fact_b_id="intra-2",
        document_a_id="doc-disagree",
        document_b_id="doc-disagree"
    )

    res = matcher.compare(fact_a, fact_b, candidate=cand)
    assert res.classification == MatchClassification.SAME_CLAIM
    assert res.signals.subject == "exact"
    assert res.signals.value == "different"

