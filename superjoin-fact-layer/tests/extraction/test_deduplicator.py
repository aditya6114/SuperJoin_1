from superjoin.extraction.models import Fact, Subject, FactValue, TimeContext
from superjoin.extraction.deduplicator import deduplicate_facts

def test_deduplicate_merges_identical_claims():
    # Identical claim mentioned in paragraph and executive summary
    f1 = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="operates",
        object=FactValue(value_type="quantity", value=93, unit="fulfilment centres"),
        time=TimeContext(time_type="unknown"),
        scope="India",
        confidence=0.90,
        evidence_ids=["p-1"]
    )
    f2 = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="operates",
        object=FactValue(value_type="quantity", value=93, unit="fulfilment centres"),
        time=TimeContext(time_type="unknown"),
        scope="India",
        confidence=0.95,
        evidence_ids=["summary-1"]
    )

    deduped = deduplicate_facts([f1, f2])
    assert len(deduped) == 1
    assert "p-1" in deduped[0].evidence_ids
    assert "summary-1" in deduped[0].evidence_ids
    assert deduped[0].confidence == 0.95  # Takes maximum confidence

def test_deduplicate_retains_different_periods():
    # Edge case 1: SAME METRIC, DIFFERENT PERIOD
    # Revenue FY2022 = 100 vs Revenue FY2023 = 120
    f1 = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=100, currency="₹", scale="million"),
        time=TimeContext(time_type="fiscal_year", value="FY2022"),
        confidence=0.9,
        evidence_ids=["p-1"]
    )
    f2 = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=120, currency="₹", scale="million"),
        time=TimeContext(time_type="fiscal_year", value="FY2023"),
        confidence=0.9,
        evidence_ids=["p-2"]
    )

    deduped = deduplicate_facts([f1, f2])
    assert len(deduped) == 2

def test_deduplicate_retains_different_scopes():
    # Consolidated operations vs Standalone operations
    f1 = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=100, currency="₹", scale="million"),
        time=TimeContext(time_type="fiscal_year", value="FY2022"),
        scope="consolidated",
        confidence=0.9,
        evidence_ids=["p-1"]
    )
    f2 = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=100, currency="₹", scale="million"),
        time=TimeContext(time_type="fiscal_year", value="FY2022"),
        scope="standalone",
        confidence=0.9,
        evidence_ids=["p-2"]
    )

    deduped = deduplicate_facts([f1, f2])
    assert len(deduped) == 2

def test_deduplicate_retains_different_units():
    # Edge case: ₹5 crore vs ₹50 million
    f1 = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=5, currency="₹", scale="crore"),
        time=TimeContext(time_type="fiscal_year", value="FY2022"),
        confidence=0.9,
        evidence_ids=["p-1"]
    )
    f2 = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=50, currency="₹", scale="million"),
        time=TimeContext(time_type="fiscal_year", value="FY2022"),
        confidence=0.9,
        evidence_ids=["p-2"]
    )

    deduped = deduplicate_facts([f1, f2])
    assert len(deduped) == 2
