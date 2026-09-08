import pytest
from pydantic import ValidationError
from superjoin.extraction.models import (
    Fact,
    Subject,
    FactValue,
    TimeContext,
    FactExtractionResult,
    ExtractionStatistics
)

def test_numerical_fact_creation():
    fact = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="operates",
        object=FactValue(
            value_type="quantity",
            value=93,
            unit="fulfilment centres"
        ),
        time=TimeContext(time_type="unknown"),
        scope="India",
        qualifiers=[],
        confidence=0.95,
        evidence_ids=["elem-001"]
    )
    assert fact.subject.name == "Delhivery"
    assert fact.predicate == "operates"
    assert fact.object.value == 93
    assert fact.object.unit == "fulfilment centres"
    assert fact.confidence == 0.95
    assert fact.evidence_ids == ["elem-001"]

def test_approximate_value_and_qualifier():
    # Edge case: "over 1,607 centres" -> value=1607, qualifier="greater_than"
    fact = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="operates_centres",
        object=FactValue(
            value_type="number",
            value=1607,
            unit="centres",
            qualifier="greater_than"
        ),
        time=TimeContext(time_type="as_of_date", value="December 31, 2021"),
        qualifiers=["over"],
        confidence=0.9,
        evidence_ids=["elem-100"]
    )
    assert fact.object.qualifier == "greater_than"
    assert "over" in fact.qualifiers
    assert fact.time.time_type == "as_of_date"
    assert fact.time.value == "December 31, 2021"

def test_temporal_context_types():
    # FY2022
    fy_time = TimeContext(time_type="fiscal_year", value="FY2022")
    assert fy_time.time_type == "fiscal_year"
    assert fy_time.value == "FY2022"

    # Unknown time
    unk_time = TimeContext(time_type="unknown")
    assert unk_time.time_type == "unknown"
    assert unk_time.value is None

    # Quarter
    q_time = TimeContext(time_type="quarter", value="Q3 FY2024")
    assert q_time.time_type == "quarter"

def test_currency_and_scale():
    fact = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(
            value_type="currency",
            value=500.0,
            currency="₹",
            scale="million"
        ),
        time=TimeContext(time_type="fiscal_year", value="FY2022"),
        scope="consolidated operations",
        qualifiers=["unaudited"],
        confidence=0.88,
        evidence_ids=["elem-rev-1"]
    )
    assert fact.object.currency == "₹"
    assert fact.object.scale == "million"
    assert fact.scope == "consolidated operations"
    assert "unaudited" in fact.qualifiers

def test_fact_requires_evidence():
    with pytest.raises(ValidationError):
        Fact(
            fact_type="semantic",
            subject=Subject(name="Delhivery", type="company"),
            predicate="operates",
            object=FactValue(value_type="text", value="Logistics"),
            time=TimeContext(time_type="unknown"),
            confidence=0.9,
            evidence_ids=[]  # Min length 1 required
        )

def test_confidence_boundary():
    with pytest.raises(ValidationError):
        Fact(
            fact_type="semantic",
            subject=Subject(name="Delhivery", type="company"),
            predicate="operates",
            object=FactValue(value_type="text", value="Logistics"),
            time=TimeContext(time_type="unknown"),
            confidence=1.5,  # Invalid: must be <= 1.0
            evidence_ids=["elem-1"]
        )

def test_entity_status_change_event():
    # Event fact: "Person resigned as director in 2024"
    fact = Fact(
        fact_type="event",
        subject=Subject(name="John Doe", type="person"),
        predicate="resigned_as",
        object=FactValue(value_type="text", value="director"),
        time=TimeContext(time_type="calendar_year", value="2024"),
        confidence=0.95,
        evidence_ids=["elem-event-1"]
    )
    assert fact.fact_type == "event"
    assert fact.predicate == "resigned_as"
    assert fact.object.value == "director"
