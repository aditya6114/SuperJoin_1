import json
import pytest
from pathlib import Path
from superjoin.ingestion.models import (
    CanonicalDocument,
    CanonicalElement,
    CanonicalPage,
    DocumentMetadata
)
from superjoin.extraction.models import (
    Fact,
    FactList,
    Subject,
    FactValue,
    TimeContext,
    FactExtractionResult
)
from superjoin.extraction.llm.provider import MockLLMProvider
from superjoin.extraction.service import FactExtractionService

def test_service_pipeline_end_to_end(tmp_path):
    meta = DocumentMetadata(
        document_id="doc-svc-001",
        filename="report.pdf",
        page_count=1,
        parser="docling",
        file_size_bytes=1500,
        sha256="abcd1234",
        processing_status="success"
    )
    elem_p1 = CanonicalElement(
        element_id="p-1",
        type="paragraph",
        canonical_order=1,
        raw_order=1,
        content="Delhivery operates 93 fulfilment centres.",
        evidence_ids=["p-1"]
    )
    page = CanonicalPage(pdf_page_number=1, elements=[elem_p1])
    doc = CanonicalDocument(document_id="doc-svc-001", source_filename="report.pdf", metadata=meta, pages=[page])

    mock_fact = Fact(
        fact_type="numerical",
        subject=Subject(name="Delhivery", type="company"),
        predicate="operates",
        object=FactValue(value_type="quantity", value=93, unit="fulfilment centres"),
        time=TimeContext(time_type="unknown"),
        confidence=0.96,
        evidence_ids=["p-1"]
    )

    mock_llm = MockLLMProvider()
    mock_llm.set_response("p-1", FactList(facts=[mock_fact]))

    service = FactExtractionService(llm_client=mock_llm, output_dir=str(tmp_path))
    result: FactExtractionResult = service.extract(doc)

    assert result.document_id == "doc-svc-001"
    assert len(result.facts) == 1
    assert result.facts[0].predicate == "operates"
    assert result.facts[0].object.value == 93
    assert result.statistics.facts_extracted == 1
    assert result.statistics.facts_rejected == 0

    # Test persistence
    saved_file = tmp_path / "doc-svc-001.json"
    assert saved_file.exists()
    saved_data = json.loads(saved_file.read_text(encoding="utf-8"))
    assert saved_data["document_id"] == "doc-svc-001"
    assert len(saved_data["facts"]) == 1

def test_integration_with_canonical_parsed_document(tmp_path):
    # Integration test with actual canonical output produced by Module 1
    canonical_path = Path("data/parsed/01-delhivery-prospectus-2022-excerpt-0d7e71.json")
    if not canonical_path.exists():
        pytest.skip("Parsed canonical sample not found.")

    with open(canonical_path, "r", encoding="utf-8") as f:
        doc_dict = json.load(f)

    doc = CanonicalDocument.model_validate(doc_dict)
    assert doc.document_id is not None
    assert len(doc.pages) > 0

    mock_llm = MockLLMProvider()
    service = FactExtractionService(llm_client=mock_llm, output_dir=str(tmp_path))
    result = service.extract(doc)

    assert result.document_id == doc.metadata.document_id
    assert result.statistics.candidate_count > 0
    assert result.statistics.candidate_count == (
        result.statistics.text_candidate_count + 
        result.statistics.table_candidate_count + 
        result.statistics.figure_candidate_count
    )
