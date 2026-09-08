from superjoin.ingestion.models import (
    CanonicalDocument,
    CanonicalElement,
    CanonicalPage,
    DocumentMetadata
)
from superjoin.extraction.models import Fact, Subject, FactValue, TimeContext
from superjoin.extraction.validators import validate_fact, validate_facts

def make_test_document() -> CanonicalDocument:
    meta = DocumentMetadata(
        document_id="doc-val-test",
        filename="val_test.pdf",
        page_count=1,
        parser="docling",
        file_size_bytes=1000,
        sha256="1234",
        processing_status="success"
    )
    elements = [
        CanonicalElement(
            element_id="valid-elem-1",
            type="paragraph",
            canonical_order=1,
            raw_order=1,
            content="Delhivery reported revenue of ₹500 million.",
            evidence_ids=["valid-ev-1"]
        ),
        CanonicalElement(
            element_id="valid-elem-2",
            type="paragraph",
            canonical_order=2,
            raw_order=2,
            content="Operates 93 fulfilment centres in India.",
            evidence_ids=["valid-ev-2"]
        )
    ]
    page = CanonicalPage(pdf_page_number=1, elements=elements)
    return CanonicalDocument(document_id="doc-val-test", source_filename="val_test.pdf", metadata=meta, pages=[page])

def test_valid_fact_passes():
    doc = make_test_document()
    fact = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=500, currency="₹", scale="million"),
        time=TimeContext(time_type="unknown"),
        confidence=0.9,
        evidence_ids=["valid-elem-1"]
    )
    is_valid, msg = validate_fact(fact, doc)
    assert is_valid
    assert msg == ""

def test_fabricated_evidence_id_fails():
    doc = make_test_document()
    fact = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="revenue",
        object=FactValue(value_type="currency", value=500, currency="₹", scale="million"),
        time=TimeContext(time_type="unknown"),
        confidence=0.9,
        evidence_ids=["fabricated-fake-element-999"]
    )
    is_valid, msg = validate_fact(fact, doc)
    assert not is_valid
    assert "fabricated-fake-element-999" in msg

def test_validate_facts_filters_rejections():
    doc = make_test_document()
    f_valid = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="operates",
        object=FactValue(value_type="quantity", value=93, unit="fulfilment centres"),
        time=TimeContext(time_type="unknown"),
        confidence=0.95,
        evidence_ids=["valid-elem-2"]
    )
    f_invalid = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="operates",
        object=FactValue(value_type="quantity", value=93, unit="fulfilment centres"),
        time=TimeContext(time_type="unknown"),
        confidence=0.95,
        evidence_ids=["unknown-evidence-id"]
    )

    valid_facts, rejections = validate_facts([f_valid, f_invalid], doc)
    assert len(valid_facts) == 1
    assert valid_facts[0].evidence_ids == ["valid-elem-2"]
    assert len(rejections) == 1
    assert "unknown-evidence-id" in rejections[0]["reason"]
