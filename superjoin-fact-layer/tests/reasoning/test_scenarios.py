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


def test_assignment_case_a_corroboration_different_units(matcher, service):
    """Case A — Corroboration: ₹5 crore vs ₹50 million in FY2024.
    Expected: CORROBORATES because units differ but value is equivalent.
    """
    fact_a = Fact(
        fact_id="case-a-1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=5, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["doc1:ev1"]
    )
    fact_b = Fact(
        fact_id="case-a-2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=50, currency="₹", scale="million"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["doc2:ev2"]
    )
    cand = CandidatePair(fact_a_id="case-a-1", fact_b_id="case-a-2", document_a_id="doc1", document_b_id="doc2")
    match = matcher.compare(fact_a, fact_b, candidate=cand)
    rel = service.reason_match(match)

    assert rel.relationship == RelationshipType.CORROBORATES
    assert rel.confidence >= 0.90
    assert "numerically equivalent" in rel.reason
    assert rel.evidence.fact_a_evidence == ["doc1:ev1"]
    assert rel.evidence.fact_b_evidence == ["doc2:ev2"]
    assert rel.source_independence == "cross_document"


def test_assignment_case_a_corroboration_compatible_approx(matcher, service):
    """Case A — Corroboration: approximately 5.0M vs 5.02M employees.
    Expected: CORROBORATES within supported approximation tolerance.
    """
    fact_a = Fact(
        fact_id="approx-1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="employee_count",
        object=FactObject(value_type="quantity", value=5.0, scale="million", qualifier="approximate"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["ev-a"]
    )
    fact_b = Fact(
        fact_id="approx-2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="employee_count",
        object=FactObject(value_type="quantity", value=5.02, scale="million"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["ev-b"]
    )
    cand = CandidatePair(fact_a_id="approx-1", fact_b_id="approx-2", document_a_id="doc1", document_b_id="doc2")
    match = matcher.compare(fact_a, fact_b, candidate=cand)
    rel = service.reason_match(match)

    assert rel.relationship == RelationshipType.CORROBORATES
    assert "approximation tolerance" in rel.reason


def test_assignment_case_b_genuine_contradiction(matcher, service):
    """Case B — Genuine Contradiction: Revenue = ₹500 Cr vs ₹600 Cr in FY2024.
    Expected: CONTRADICTS when entity, metric, period, and scope are identical.
    """
    fact_a = Fact(
        fact_id="case-b-1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["ev-a"]
    )
    fact_b = Fact(
        fact_id="case-b-2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=600, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["ev-b"]
    )
    cand = CandidatePair(fact_a_id="case-b-1", fact_b_id="case-b-2", document_a_id="doc1", document_b_id="doc2")
    match = matcher.compare(fact_a, fact_b, candidate=cand)
    rel = service.reason_match(match)

    assert rel.relationship == RelationshipType.CONTRADICTS
    assert rel.confidence >= 0.85
    assert "materially different values" in rel.reason
    assert "mutually incompatible" in rel.explanation


def test_assignment_case_c_reconciled_by_time(matcher, service):
    """Case C — Contextual Reconciliation: Revenue FY2023 = ₹500 Cr vs FY2024 = ₹600 Cr.
    Expected: CONTEXTUALLY_RECONCILED due to different reporting periods.
    """
    fact_a = Fact(
        fact_id="case-c-1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2023"),
        confidence=0.95,
        evidence_ids=["ev-a"]
    )
    fact_b = Fact(
        fact_id="case-c-2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=600, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["ev-b"]
    )
    cand = CandidatePair(fact_a_id="case-c-1", fact_b_id="case-c-2", document_a_id="doc1", document_b_id="doc2")
    match = matcher.compare(fact_a, fact_b, candidate=cand)
    rel = service.reason_match(match)

    assert rel.relationship == RelationshipType.CONTEXTUALLY_RECONCILED
    assert "different reporting periods" in rel.reason
    assert "FY2023" in rel.explanation
    assert "FY2024" in rel.explanation


def test_assignment_case_c_reconciled_by_scope(matcher, service):
    """Case C — Contextual Reconciliation: Consolidated ₹100 Cr vs India segment ₹30 Cr.
    Expected: CONTEXTUALLY_RECONCILED due to differing scope.
    """
    fact_a = Fact(
        fact_id="scope-1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=100, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        scope="consolidated",
        confidence=0.95,
        evidence_ids=["ev-a"]
    )
    fact_b = Fact(
        fact_id="scope-2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=30, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        scope="India segment",
        confidence=0.95,
        evidence_ids=["ev-b"]
    )
    cand = CandidatePair(fact_a_id="scope-1", fact_b_id="scope-2", document_a_id="doc1", document_b_id="doc2")
    match = matcher.compare(fact_a, fact_b, candidate=cand)
    rel = service.reason_match(match)

    assert rel.relationship == RelationshipType.CONTEXTUALLY_RECONCILED
    assert "different reporting scopes" in rel.reason
    assert "consolidated" in rel.explanation
    assert "India segment" in rel.explanation


def test_assignment_case_c_reconciled_by_status_transition(matcher, service):
    """Case C — Contextual Reconciliation: Alice appointed CEO 2021 vs resigned CEO 2024.
    Expected: CONTEXTUALLY_RECONCILED as status transition.
    """
    fact_a = Fact(
        fact_id="status-1",
        fact_type="event",
        subject=FactSubject(name="Alice", type="person"),
        predicate="appointed",
        object=FactObject(value_type="text", value="CEO"),
        time=TemporalContext(time_type="calendar_year", value="2021"),
        confidence=0.90,
        evidence_ids=["ev-a"]
    )
    fact_b = Fact(
        fact_id="status-2",
        fact_type="event",
        subject=FactSubject(name="Alice", type="person"),
        predicate="resigned",
        object=FactObject(value_type="text", value="CEO"),
        time=TemporalContext(time_type="calendar_year", value="2024"),
        confidence=0.90,
        evidence_ids=["ev-b"]
    )
    cand = CandidatePair(fact_a_id="status-1", fact_b_id="status-2", document_a_id="doc1", document_b_id="doc2")
    match = matcher.compare(fact_a, fact_b, candidate=cand)
    rel = service.reason_match(match)

    assert rel.relationship == RelationshipType.CONTEXTUALLY_RECONCILED
    assert "status transition" in rel.reason
    assert "appointed" in rel.explanation
    assert "resigned" in rel.explanation


def test_assignment_case_d_unresolved_unknown_subject(matcher, service):
    """Case D — Failure Handling: 'It operates 50 stores' vs 'Company X operates 60 stores'.
    Expected: UNRESOLVED because subject of 'It' is unresolved pronoun.
    """
    fact_a = Fact(
        fact_id="pronoun-1",
        fact_type="numerical",
        subject=FactSubject(name="It", type="company"),
        predicate="operates",
        object=FactObject(value_type="quantity", value=50, unit="stores"),
        time=TemporalContext(time_type="unknown"),
        confidence=0.85,
        evidence_ids=["ev-a"]
    )
    fact_b = Fact(
        fact_id="pronoun-2",
        fact_type="numerical",
        subject=FactSubject(name="Company X", type="company"),
        predicate="operates",
        object=FactObject(value_type="quantity", value=60, unit="stores"),
        time=TemporalContext(time_type="unknown"),
        confidence=0.90,
        evidence_ids=["ev-b"]
    )
    cand = CandidatePair(fact_a_id="pronoun-1", fact_b_id="pronoun-2", document_a_id="doc1", document_b_id="doc2")
    match = matcher.compare(fact_a, fact_b, candidate=cand)
    rel = service.reason_match(match)

    assert rel.relationship == RelationshipType.UNRESOLVED
    assert "unresolved" in rel.reason.lower()


def test_assignment_case_d_unresolved_missing_context(matcher, service):
    """Case D — Failure Handling: Revenue ₹500 Cr vs ₹600 Cr, but time=unknown and scope=unknown.
    Expected: UNRESOLVED rather than false contradiction.
    """
    fact_a = Fact(
        fact_id="unk-time-1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="unknown"),
        confidence=0.95,
        evidence_ids=["ev-a"]
    )
    fact_b = Fact(
        fact_id="unk-time-2",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=600, currency="₹", scale="crore"),
        time=TemporalContext(time_type="unknown"),
        confidence=0.95,
        evidence_ids=["ev-b"]
    )
    cand = CandidatePair(fact_a_id="unk-time-1", fact_b_id="unk-time-2", document_a_id="doc1", document_b_id="doc2")
    match = matcher.compare(fact_a, fact_b, candidate=cand)
    rel = service.reason_match(match)

    assert rel.relationship == RelationshipType.UNRESOLVED
    assert "values differ, but available evidence does not establish" in rel.reason


def test_unrelated_different_entities(matcher, service):
    """Unrelated claims: Delhivery revenue vs Amazon revenue.
    Expected: UNRELATED.
    """
    fact_a = Fact(
        fact_id="delhivery-1",
        fact_type="numerical",
        subject=FactSubject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["ev-a"]
    )
    fact_b = Fact(
        fact_id="amazon-1",
        fact_type="numerical",
        subject=FactSubject(name="Amazon", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=600, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["ev-b"]
    )
    cand = CandidatePair(fact_a_id="delhivery-1", fact_b_id="amazon-1", document_a_id="doc1", document_b_id="doc2")
    match = matcher.compare(fact_a, fact_b, candidate=cand)
    rel = service.reason_match(match)

    assert rel.relationship == RelationshipType.UNRELATED
    assert "different entities" in rel.reason
