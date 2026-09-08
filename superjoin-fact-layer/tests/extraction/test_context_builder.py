import json
from superjoin.ingestion.models import (
    CanonicalDocument,
    CanonicalElement,
    CanonicalTable,
    CanonicalFigure,
    CanonicalPage,
    DocumentMetadata
)
from superjoin.extraction.context_builder import build_context, find_section_hierarchy

def test_context_builder_for_text_with_hierarchy():
    meta = DocumentMetadata(
        document_id="doc-123",
        filename="prospectus.pdf",
        title="Prospectus 2022",
        page_count=2,
        parser="docling",
        file_size_bytes=5000,
        sha256="xyz",
        processing_status="success"
    )
    elements = [
        CanonicalElement(
            element_id="sec-1",
            type="section_header",
            canonical_order=1,
            raw_order=1,
            content="Our Business",
            evidence_ids=["ev-sec1"]
        ),
        CanonicalElement(
            element_id="sec-2",
            type="section_header",
            canonical_order=2,
            raw_order=2,
            content="Network Infrastructure",
            evidence_ids=["ev-sec2"]
        ),
        CanonicalElement(
            element_id="p-1",
            type="paragraph",
            canonical_order=3,
            raw_order=3,
            content="Delhivery operates 93 fulfilment centres.",
            evidence_ids=["ev-p1"]
        )
    ]
    page = CanonicalPage(pdf_page_number=5, printed_page_number=3, elements=elements)
    doc = CanonicalDocument(document_id="doc-123", source_filename="prospectus.pdf", metadata=meta, pages=[page])

    ctx_str = build_context(doc, elements[2])
    ctx = json.loads(ctx_str)

    assert ctx["document_id"] == "doc-123"
    assert ctx["element_id"] == "p-1"
    assert ctx["pdf_page_number"] == 5
    assert ctx["printed_page_number"] == 3
    assert ctx["preceding_section_header"] == "Network Infrastructure"
    assert "Our Business" in ctx["section_hierarchy"]
    assert "Delhivery operates 93 fulfilment centres." in ctx["content"]
    assert ctx["evidence_ids"] == ["ev-p1"]

def test_context_builder_for_table():
    meta = DocumentMetadata(
        document_id="doc-tbl",
        filename="report.pdf",
        page_count=1,
        parser="docling",
        file_size_bytes=2000,
        sha256="abc",
        processing_status="success"
    )
    tbl = CanonicalTable(
        element_id="t-1",
        canonical_order=1,
        raw_order=1,
        content="Table",
        evidence_ids=["ev-t1"],
        caption="Financial Highlights (₹ in million)",
        headers=["Fiscal Year", "Revenue"],
        rows=[["FY2022", "1000"], ["FY2023", "1200"]],
        source="Company filings"
    )
    page = CanonicalPage(pdf_page_number=1, elements=[tbl])
    doc = CanonicalDocument(document_id="doc-tbl", source_filename="report.pdf", metadata=meta, pages=[page])

    ctx_str = build_context(doc, tbl)
    ctx = json.loads(ctx_str)

    assert ctx["element_type"] == "table"
    assert ctx["table_caption"] == "Financial Highlights (₹ in million)"
    assert ctx["table_headers"] == ["Fiscal Year", "Revenue"]
    assert len(ctx["table_rows"]) == 2
    assert ctx["table_source"] == "Company filings"
