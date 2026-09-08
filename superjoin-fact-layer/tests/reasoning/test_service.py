import pytest
import json
from pathlib import Path
from superjoin.extraction.models import Fact, FactSubject, FactObject, TemporalContext
from superjoin.matching.models import MatchResult, MatchSignals, MatchClassification, MatchingSessionResult
from superjoin.reasoning.models import RelationshipType
from superjoin.reasoning.service import RelationshipReasoningService


@pytest.fixture
def service(tmp_path):
    return RelationshipReasoningService(output_dir=tmp_path / "relationships")


def test_service_reason_matches(service):
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
        object=FactObject(value_type="currency", value=500, currency="₹", scale="crore"),
        time=TemporalContext(time_type="fiscal_year", value="FY2024"),
        confidence=0.95,
        evidence_ids=["e2"]
    )
    signals = MatchSignals(
        subject="exact", predicate="exact", fact_type="compatible",
        value="equal", unit="same", time="same", scope="same", qualifiers="exact"
    )
    match = MatchResult(
        fact_a_id="f1",
        fact_b_id="f2",
        document_a_id="doc1",
        document_b_id="doc2",
        classification=MatchClassification.SAME_CLAIM,
        confidence=0.95,
        signals=signals,
        reasons=["Same claim"],
        fact_a=fact_a,
        fact_b=fact_b
    )

    session_res = service.reason_matches([match])
    assert len(session_res.relationships) == 1
    assert session_res.relationships[0].relationship == RelationshipType.CORROBORATES
    assert session_res.statistics.corroborates == 1
    assert session_res.statistics.total_pairs == 1


def test_service_save_results(service, tmp_path):
    signals = MatchSignals(
        subject="exact", predicate="exact", fact_type="compatible",
        value="equal", unit="same", time="same", scope="same", qualifiers="exact"
    )
    match = MatchResult(
        fact_a_id="f1",
        fact_b_id="f2",
        document_a_id="doc1",
        document_b_id="doc2",
        classification=MatchClassification.SAME_CLAIM,
        confidence=0.95,
        signals=signals,
        reasons=["Same claim"],
    )
    session_res = service.reason_matches([match])
    out_file = service.save_results(session_res, output_path=tmp_path / "out.json")
    assert out_file.exists()

    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["relationships"]) == 1
    assert data["statistics"]["total_pairs"] == 1
