import pytest
from superjoin.extraction.models import Fact, Subject, FactValue, TimeContext, FactExtractionResult
from superjoin.matching.index import FactIndex, normalize_key


def make_fact(fact_id: str, subject: str, predicate: str, val: float = 100.0, time_val: str = "FY2024") -> Fact:
    return Fact(
        fact_id=fact_id,
        fact_type="numerical",
        subject=Subject(name=subject, type="company"),
        predicate=predicate,
        object=FactValue(value_type="currency", value=val, currency="₹", scale="crore"),
        time=TimeContext(time_type="fiscal_year", value=time_val),
        confidence=0.95,
        evidence_ids=["ev-1"]
    )


def test_index_single_fact():
    index = FactIndex()
    f1 = make_fact("F001", "Delhivery", "revenue", 500)
    index.add_fact(f1, "doc_1")

    assert len(index) == 1
    assert "F001" in index
    assert index.get("F001") == f1
    assert index.get_document_id("F001") == "doc_1"
    assert index.by_document("doc_1") == [f1]
    assert index.by_subject("Delhivery") == [f1]
    assert index.by_predicate("revenue") == [f1]
    assert index.by_subject_predicate("Delhivery", "revenue") == [f1]


def test_index_multiple_facts_and_documents():
    index = FactIndex()
    f1 = make_fact("F001", "Delhivery", "revenue", 500)
    f2 = make_fact("F002", "Delhivery", "employee_count", 50000)
    f3 = make_fact("F003", "Delhivery", "revenue", 600)
    f4 = make_fact("F004", "Amazon", "revenue", 1000)

    index.add_fact(f1, "doc_1")
    index.add_fact(f2, "doc_1")
    index.add_fact(f3, "doc_2")
    index.add_fact(f4, "doc_3")

    assert len(index) == 4
    assert len(index.by_document("doc_1")) == 2
    assert len(index.by_document("doc_2")) == 1
    assert len(index.by_document("doc_3")) == 1

    assert index.by_subject("Delhivery") == [f1, f2, f3]
    assert index.by_subject("Amazon") == [f4]

    assert index.by_predicate("revenue") == [f1, f3, f4]
    assert index.by_predicate("employee_count") == [f2]

    assert index.by_subject_predicate("Delhivery", "revenue") == [f1, f3]
    assert index.by_subject_predicate("Amazon", "revenue") == [f4]
    assert index.by_subject_predicate("Delhivery", "employee_count") == [f2]


def test_duplicate_subjects_and_predicates():
    index = FactIndex()
    f1 = make_fact("F001", "Delhivery", "revenue", 500)
    f2 = make_fact("F002", "delhivery", "REVENUE", 600)

    index.add_fact(f1, "doc_1")
    index.add_fact(f2, "doc_2")

    assert len(index.by_subject("DELHIVERY")) == 2
    assert len(index.by_predicate("Revenue")) == 2
    assert len(index.by_subject_predicate("Delhivery", "revenue")) == 2


def test_missing_fact_ids_and_none():
    index = FactIndex()
    assert index.get("non_existent") is None
    assert index.get_document_id("non_existent") is None
    assert index.by_document("non_existent") == []
    assert index.by_subject("non_existent") == []
    assert index.by_predicate("non_existent") == []
    assert index.by_subject_predicate("non_existent", "non_existent") == []

    # Fact with empty fact_id or None
    index.add_fact(None, "doc_1")
    assert len(index) == 0


def test_empty_collections():
    index = FactIndex()
    assert len(index) == 0
    assert index.all_facts() == []
    assert index.documents() == set()
    assert index.subjects() == set()
    assert index.predicates() == set()


def test_normalization():
    assert normalize_key("  Delhivery Limited \n") == "delhivery limited"
    assert normalize_key(None) == ""
    assert normalize_key("REVENUE") == "revenue"


def test_index_extraction_result():
    index = FactIndex()
    f1 = make_fact("F001", "Delhivery", "revenue", 500)
    f2 = make_fact("F002", "Delhivery", "profit", 50)
    result = FactExtractionResult(document_id="doc_prospectus", facts=[f1, f2])

    index.index_extraction_result(result)
    assert len(index) == 2
    assert index.by_document("doc_prospectus") == [f1, f2]
