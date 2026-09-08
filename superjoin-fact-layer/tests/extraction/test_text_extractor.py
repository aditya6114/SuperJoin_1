import json
from superjoin.extraction.models import Fact, FactList, Subject, FactValue, TimeContext
from superjoin.extraction.llm.provider import MockLLMProvider
from superjoin.extraction.extractors.text_extractor import extract_text_facts

def test_extract_atomic_facts_from_text():
    context = json.dumps({
        "document_id": "doc-delhivery",
        "element_id": "elem-p1",
        "evidence_ids": ["elem-p1"],
        "content": "Delhivery operates 93 fulfilment centres covering 6.25 million square feet."
    })

    # Mock LLM returns two atomic facts
    fact_a = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="operates",
        object=FactValue(value_type="quantity", value=93, unit="fulfilment centres"),
        time=TimeContext(time_type="unknown"),
        confidence=0.95,
        evidence_ids=["elem-p1"]
    )
    fact_b = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="has_floor_area",
        object=FactValue(value_type="number", value=6.25, unit="million square feet", scale="million"),
        time=TimeContext(time_type="unknown"),
        confidence=0.92,
        evidence_ids=["elem-p1"]
    )

    mock_client = MockLLMProvider()
    mock_client.set_response("elem-p1", FactList(facts=[fact_a, fact_b]))

    extracted = extract_text_facts(context, mock_client)

    assert len(extracted) == 2
    assert extracted[0].predicate == "operates"
    assert extracted[0].object.value == 93
    assert extracted[1].predicate == "has_floor_area"
    assert extracted[1].object.value == 6.25
    assert extracted[0].evidence_ids == ["elem-p1"]
    assert extracted[1].evidence_ids == ["elem-p1"]

def test_extract_text_attaches_fallback_evidence_if_missing():
    context = json.dumps({
        "element_id": "el-99",
        "evidence_ids": ["el-99"],
        "content": "Revenue was ₹1,000 crore."
    })
    # Fact returned without explicit evidence_ids
    fact_without_ev = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=1000, currency="₹", scale="crore"),
        time=TimeContext(time_type="unknown"),
        confidence=0.9,
        evidence_ids=["temp"]  # will be replaced or tested
    )
    fact_without_ev.evidence_ids = []

    mock_client = MockLLMProvider()
    mock_client.set_response("el-99", FactList(facts=[fact_without_ev]))

    extracted = extract_text_facts(context, mock_client)
    assert len(extracted) == 1
    assert "el-99" in extracted[0].evidence_ids
