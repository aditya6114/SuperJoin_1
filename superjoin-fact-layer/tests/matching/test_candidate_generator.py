import pytest
from superjoin.extraction.models import Fact, Subject, FactValue, TimeContext
from superjoin.matching.index import FactIndex
from superjoin.matching.candidate_generator import CandidateGenerator


def make_fact(fact_id: str, subject: str, predicate: str, val: float = 100.0, time_val: str = "FY2024", f_type: str = "numerical", v_type: str = "currency") -> Fact:
    return Fact(
        fact_id=fact_id,
        fact_type=f_type,
        subject=Subject(name=subject, type="company"),
        predicate=predicate,
        object=FactValue(value_type=v_type, value=val, currency="₹", scale="crore"),
        time=TimeContext(time_type="fiscal_year", value=time_val),
        confidence=0.95,
        evidence_ids=["ev-1"]
    )


def test_cross_document_filtering():
    index = FactIndex()
    f1 = make_fact("F1", "Delhivery", "revenue", 500)
    f2 = make_fact("F2", "Delhivery", "revenue", 600)
    f3 = make_fact("F3", "Delhivery", "revenue", 700)

    # F1 and F2 are in doc1, F3 is in doc2
    index.add_fact(f1, "doc1")
    index.add_fact(f2, "doc1")
    index.add_fact(f3, "doc2")

    gen = CandidateGenerator(cross_document_only=True)
    candidates = gen.generate_candidates(index)

    pair_ids = [(c.fact_a_id, c.fact_b_id) for c in candidates]
    # (F1, F2) should NOT be present because they are both in doc1
    assert ("F1", "F2") not in pair_ids and ("F2", "F1") not in pair_ids

    # (F1, F3) and (F2, F3) should be present
    assert len(candidates) == 2
    assert any(set([c.fact_a_id, c.fact_b_id]) == {"F1", "F3"} for c in candidates)
    assert any(set([c.fact_a_id, c.fact_b_id]) == {"F2", "F3"} for c in candidates)


def test_intra_document_when_cross_doc_disabled():
    index = FactIndex()
    f1 = make_fact("F1", "Delhivery", "revenue", 500)
    f2 = make_fact("F2", "Delhivery", "revenue", 600)

    index.add_fact(f1, "doc1")
    index.add_fact(f2, "doc1")

    gen = CandidateGenerator(cross_document_only=False)
    candidates = gen.generate_candidates(index)

    assert len(candidates) == 1
    assert set([candidates[0].fact_a_id, candidates[0].fact_b_id]) == {"F1", "F2"}


def test_preserves_different_values_and_times():
    index = FactIndex()
    # Different values: 500 vs 600
    f1 = make_fact("F1", "Delhivery", "revenue", 500, time_val="FY2023")
    # Different time: FY2023 vs FY2024
    f2 = make_fact("F2", "Delhivery", "revenue", 600, time_val="FY2024")

    index.add_fact(f1, "doc1")
    index.add_fact(f2, "doc2")

    gen = CandidateGenerator(cross_document_only=True)
    candidates = gen.generate_candidates(index)

    assert len(candidates) == 1
    assert candidates[0].signals["subject"] == "exact"
    assert candidates[0].signals["predicate"] == "exact"


def test_incompatible_entities_not_paired():
    index = FactIndex()
    f1 = make_fact("F1", "Delhivery", "revenue", 500)
    f2 = make_fact("F2", "Amazon", "revenue", 600)

    index.add_fact(f1, "doc1")
    index.add_fact(f2, "doc2")

    gen = CandidateGenerator(cross_document_only=True)
    candidates = gen.generate_candidates(index)

    # Different entities (Delhivery vs Amazon) must not be paired
    assert len(candidates) == 0


def test_uncertain_subject_paired_with_known_entity():
    index = FactIndex()
    # Document 1 has unresolved pronoun 'It'
    f1 = make_fact("F1", "It", "operates", 50, f_type="numerical", v_type="quantity")
    # Document 2 has explicit subject 'Delhivery'
    f2 = make_fact("F2", "Delhivery", "operates", 93, f_type="numerical", v_type="quantity")

    index.add_fact(f1, "doc1")
    index.add_fact(f2, "doc2")

    gen = CandidateGenerator(cross_document_only=True, allow_uncertain_subject=True)
    candidates = gen.generate_candidates(index)

    assert len(candidates) == 1
    assert candidates[0].signals["subject"] == "uncertain"
    assert candidates[0].signals["predicate"] == "exact"


def test_incompatible_fact_types_not_paired():
    index = FactIndex()
    f1 = make_fact("F1", "Delhivery", "established_date", 2011, f_type="event", v_type="date")
    f2 = make_fact("F2", "Delhivery", "established_date", 500, f_type="numerical", v_type="currency")

    index.add_fact(f1, "doc1")
    index.add_fact(f2, "doc2")

    gen = CandidateGenerator(cross_document_only=True)
    candidates = gen.generate_candidates(index)

    # Date event vs currency numerical should not be paired
    assert len(candidates) == 0


def test_no_self_pairs_generated():
    """Breakpoint 11 Test 4 — Self-pairs (fact paired with itself) are never generated."""
    index = FactIndex()
    f1 = make_fact("F1", "Delhivery", "revenue", 500)
    index.add_fact(f1, "doc1")

    gen = CandidateGenerator(cross_document_only=False)
    candidates = gen.generate_candidates(index)

    assert len(candidates) == 0
