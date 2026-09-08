import pytest
from superjoin.extraction.models import Fact, Subject, FactValue, TimeContext, TemporalContext
from superjoin.matching.models import MatchClassification
from superjoin.matching.deterministic_matcher import DeterministicMatcher


def make_fact(
    fact_id: str,
    subject: str,
    predicate: str,
    val: any,
    v_type: str = "currency",
    scale: str = "crore",
    currency: str = "₹",
    time_val: str = "FY2024",
    time_type: str = "fiscal_year",
    scope: str = None,
    qualifiers: list = None,
    f_type: str = "numerical",
    confidence: float = 0.95
) -> Fact:
    return Fact(
        fact_id=fact_id,
        fact_type=f_type,
        subject=Subject(name=subject, type="company"),
        predicate=predicate,
        object=FactValue(
            value_type=v_type,
            value=val,
            currency=currency,
            scale=scale
        ),
        time=TemporalContext(time_type=time_type, value=time_val),
        scope=scope,
        qualifiers=qualifiers or [],
        confidence=confidence,
        evidence_ids=["ev-1"]
    )


def test_same_claim_equivalent_units():
    matcher = DeterministicMatcher()
    # ₹5 crore in FY2024
    f1 = make_fact("F1", "Delhivery", "revenue", 5, scale="crore", time_val="FY2024")
    # ₹50 million in FY2024
    f2 = make_fact("F2", "Delhivery", "revenue", 50, scale="million", time_val="FY2024")

    res = matcher.compare(f1, f2)
    assert res.classification == MatchClassification.SAME_CLAIM
    assert res.signals.subject == "exact"
    assert res.signals.predicate == "exact"
    assert res.signals.value == "equivalent"
    assert res.signals.time == "same"
    assert len(res.reasons) > 0


def test_genuine_contradiction_candidate_is_same_claim():
    # Section 15 Requirement:
    # Conflicting values for identical claim proposition must be SAME_CLAIM with value=different
    matcher = DeterministicMatcher()
    f1 = make_fact("F1", "Delhivery", "revenue", 500, scale="crore", time_val="FY2024")
    f2 = make_fact("F2", "Delhivery", "revenue", 600, scale="crore", time_val="FY2024")

    res = matcher.compare(f1, f2)
    assert res.classification == MatchClassification.SAME_CLAIM
    assert res.signals.value == "different"
    assert res.signals.subject == "exact"
    assert res.signals.predicate == "exact"
    assert res.signals.time == "same"


def test_different_reporting_period_is_related_claim():
    matcher = DeterministicMatcher()
    f1 = make_fact("F1", "Delhivery", "revenue", 500, scale="crore", time_val="FY2023")
    f2 = make_fact("F2", "Delhivery", "revenue", 600, scale="crore", time_val="FY2024")

    res = matcher.compare(f1, f2)
    assert res.classification == MatchClassification.RELATED_CLAIM
    assert res.signals.time == "different"


def test_different_scope_is_related_claim():
    matcher = DeterministicMatcher()
    f1 = make_fact("F1", "Delhivery", "revenue", 100, scale="crore", scope="consolidated")
    f2 = make_fact("F2", "Delhivery", "revenue", 30, scale="crore", scope="India segment")

    res = matcher.compare(f1, f2)
    assert res.classification == MatchClassification.RELATED_CLAIM
    assert res.signals.scope == "different"


def test_different_entities_is_not_match():
    matcher = DeterministicMatcher()
    f1 = make_fact("F1", "Delhivery", "revenue", 500)
    f2 = make_fact("F2", "Amazon", "revenue", 600)

    res = matcher.compare(f1, f2)
    assert res.classification == MatchClassification.NOT_MATCH
    assert res.signals.subject == "different"


def test_unknown_subject_is_uncertain():
    matcher = DeterministicMatcher()
    f1 = make_fact("F1", "It", "operates", 50, v_type="quantity", scale=None, currency=None)
    f2 = make_fact("F2", "Delhivery", "operates", 93, v_type="quantity", scale=None, currency=None)

    res = matcher.compare(f1, f2)
    assert res.classification == MatchClassification.UNCERTAIN
    assert res.signals.subject == "unknown"


def test_status_transition_is_related_claim():
    matcher = DeterministicMatcher()
    f1 = Fact(
        fact_id="F1",
        fact_type="event",
        subject=Subject(name="Alice", type="person"),
        predicate="appointed_ceo",
        object=FactValue(value_type="text", value="CEO"),
        time=TemporalContext(time_type="calendar_year", value="2021"),
        confidence=0.9,
        evidence_ids=["e1"]
    )
    f2 = Fact(
        fact_id="F2",
        fact_type="event",
        subject=Subject(name="Alice", type="person"),
        predicate="resigned_ceo",
        object=FactValue(value_type="text", value="CEO"),
        time=TemporalContext(time_type="calendar_year", value="2024"),
        confidence=0.9,
        evidence_ids=["e2"]
    )

    res = matcher.compare(f1, f2)
    assert res.classification == MatchClassification.RELATED_CLAIM
