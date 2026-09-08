import json
from superjoin.extraction.models import Fact, FactList, Subject, FactValue, TimeContext
from superjoin.extraction.llm.provider import MockLLMProvider
from superjoin.extraction.extractors.table_extractor import extract_table_facts

def test_extract_table_facts_with_inherited_units_and_time():
    context = json.dumps({
        "element_id": "tbl-rev-1",
        "evidence_ids": ["tbl-rev-1"],
        "table_caption": "Revenue and Growth (₹ in million)",
        "table_headers": ["Year", "Revenue", "Growth"],
        "table_rows": [
            ["2022", "100", "10%"],
            ["2023", "120", "20%"]
        ]
    })

    # Expected facts preserve:
    # 2022 -> revenue -> 100
    # 2022 -> growth -> 10%
    # 2023 -> revenue -> 120
    # 2023 -> growth -> 20%
    f1 = Fact(
        fact_type="numerical",
        subject=Subject(name="Company", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=100, currency="₹", scale="million"),
        time=TimeContext(time_type="calendar_year", value="2022"),
        confidence=0.95,
        evidence_ids=["tbl-rev-1"]
    )
    f2 = Fact(
        fact_type="numerical",
        subject=Subject(name="Company", type="company"),
        predicate="growth",
        object=FactValue(value_type="percentage", value=10.0, unit="%"),
        time=TimeContext(time_type="calendar_year", value="2022"),
        confidence=0.95,
        evidence_ids=["tbl-rev-1"]
    )
    f3 = Fact(
        fact_type="numerical",
        subject=Subject(name="Company", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=120, currency="₹", scale="million"),
        time=TimeContext(time_type="calendar_year", value="2023"),
        confidence=0.95,
        evidence_ids=["tbl-rev-1"]
    )
    f4 = Fact(
        fact_type="numerical",
        subject=Subject(name="Company", type="company"),
        predicate="growth",
        object=FactValue(value_type="percentage", value=20.0, unit="%"),
        time=TimeContext(time_type="calendar_year", value="2023"),
        confidence=0.95,
        evidence_ids=["tbl-rev-1"]
    )

    mock_client = MockLLMProvider()
    mock_client.set_response("tbl-rev-1", FactList(facts=[f1, f2, f3, f4]))

    extracted = extract_table_facts(context, mock_client)

    assert len(extracted) == 4
    # Check 2022 revenue
    assert extracted[0].time.value == "2022"
    assert extracted[0].object.currency == "₹"
    assert extracted[0].object.scale == "million"
    assert extracted[0].object.value == 100

    # Check 2023 revenue
    assert extracted[2].time.value == "2023"
    assert extracted[2].object.value == 120
    assert extracted[2].object.currency == "₹"
