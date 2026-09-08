from superjoin.ingestion.models import (
    CanonicalDocument,
    CanonicalElement,
    CanonicalPage,
    DocumentMetadata
)
from superjoin.extraction.service import FactExtractionService

def test_llm_off_mode_extracts_structured_facts_deterministically():
    meta = DocumentMetadata(
        document_id="doc-llm-off",
        filename="report.pdf",
        page_count=1,
        parser="docling",
        file_size_bytes=500,
        sha256="1234abcd",
        processing_status="success"
    )
    elem_text = CanonicalElement(
        element_id="p-10",
        type="paragraph",
        canonical_order=1,
        raw_order=1,
        content="Delhivery operates 93 fulfilment centres covering 6.25 million square feet in FY2022.",
        evidence_ids=["p-10"]
    )
    elem_uncertain = CanonicalElement(
        element_id="p-11",
        type="paragraph",
        canonical_order=2,
        raw_order=2,
        content="It operates 50 facilities.",
        evidence_ids=["p-11"]
    )
    doc = CanonicalDocument(
        document_id="doc-llm-off",
        source_filename="report.pdf",
        metadata=meta,
        pages=[CanonicalPage(pdf_page_number=1, elements=[elem_text, elem_uncertain])]
    )

    # Initialize service with llm_enabled=False and llm_client=None
    service = FactExtractionService(llm_client=None, llm_enabled=False)
    result = service.extract(doc)

    assert result.document_id == "doc-llm-off"
    # Extracted facts from deterministic path
    assert len(result.facts) == 2
    assert result.facts[0].predicate == "operates"
    assert result.facts[0].object.value == 93
    assert result.facts[1].predicate == "floor_area"
    assert result.facts[1].object.value == 6.25

    # Uncertain candidate recorded
    assert len(result.uncertain_candidates) >= 1
    assert any(u["element_id"] == "p-11" for u in result.uncertain_candidates)
    assert result.statistics.candidate_count == 2
