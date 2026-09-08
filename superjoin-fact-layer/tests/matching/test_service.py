import json
from pathlib import Path
import pytest
from superjoin.extraction.models import (
    Fact,
    Subject,
    FactValue,
    TemporalContext,
    FactExtractionResult
)
from superjoin.matching.service import FactMatchingService
from superjoin.matching.models import MatchClassification


def test_service_matching_workflow(tmp_path):
    f1 = Fact(
        fact_id="f1",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=5, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e1"]
    )
    f2 = Fact(
        fact_id="f2",
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=50, currency="₹", scale="million"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.92,
        evidence_ids=["e2"]
    )

    doc_a = FactExtractionResult(document_id="doc-a", facts=[f1])
    doc_b = FactExtractionResult(document_id="doc-b", facts=[f2])

    service = FactMatchingService(output_dir=tmp_path)
    session = service.match([doc_a, doc_b])

    assert session.statistics.total_documents == 2
    assert session.statistics.total_facts == 2
    assert session.statistics.candidate_pairs == 1
    assert session.statistics.same_claim_count == 1
    assert len(session.matches) == 1

    match = session.matches[0]
    assert match.classification == MatchClassification.SAME_CLAIM
    assert match.signals.value == "equivalent"
    assert match.fact_a.fact_id == "f1" or match.fact_b.fact_id == "f1"

    # Persistence verification
    saved_file = service.save_results(session, filename="test_matches.json")
    assert saved_file.exists()

    with open(saved_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert len(loaded["matches"]) == 1
    assert loaded["statistics"]["same_claim_count"] == 1


def test_service_with_actual_facts_files(tmp_path):
    facts_dir = Path("data/facts")
    if not facts_dir.exists():
        pytest.skip("data/facts directory not found")

    service = FactMatchingService(output_dir=tmp_path)
    extraction_results = service.load_from_dir(facts_dir)
    assert len(extraction_results) > 0

    session = service.match(extraction_results)
    assert session.statistics.total_facts > 0
    assert session.statistics.total_documents == len(extraction_results)
    assert session.statistics.execution_time_ms >= 0.0

    # Ensure result is saved without error
    out_file = service.save_results(session)
    assert out_file.exists()
