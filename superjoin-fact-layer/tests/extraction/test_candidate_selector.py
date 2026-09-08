from superjoin.ingestion.models import (
    CanonicalDocument,
    CanonicalElement,
    CanonicalTable,
    CanonicalFigure,
    CanonicalPage,
    DocumentMetadata
)
from superjoin.extraction.candidate_selector import (
    contains_numeric_signal,
    contains_temporal_signal,
    contains_fact_predicate,
    is_noise_or_boilerplate,
    is_fact_bearing_text,
    is_relevant_table,
    is_relevant_figure,
    calculate_candidate_priority,
    select_candidates
)

def test_numeric_signal():
    assert contains_numeric_signal("Revenue was ₹500 million.")
    assert contains_numeric_signal("Operates 93 fulfilment centres")
    assert contains_numeric_signal("Growth was 15.4%")
    assert not contains_numeric_signal("General company introduction and background.")

def test_temporal_signal():
    assert contains_temporal_signal("For the year ended March 31, 2022")
    assert contains_temporal_signal("Revenue in FY2023 was higher")
    assert contains_temporal_signal("Q3 results were positive")
    assert not contains_temporal_signal("The company provides supply chain services.")

def test_fact_predicate():
    assert contains_fact_predicate("Delhivery operates fulfillment centres")
    assert contains_fact_predicate("Company acquired Spoton Logistics")
    assert contains_fact_predicate("EBITDA margin improved")
    assert not contains_fact_predicate("Please find details in the next section.")

def test_boilerplate_and_noise_filtering():
    assert is_noise_or_boilerplate("Table of Contents")
    assert is_noise_or_boilerplate("Page 12 of 150")
    assert is_noise_or_boilerplate("- 45 -")
    assert is_noise_or_boilerplate("All rights reserved")
    # Low alphanumeric ratio OCR noise
    assert is_noise_or_boilerplate("~#^&*(@!~#^&*(")

def test_priority_ordering():
    table = CanonicalTable(
        element_id="tbl-1",
        canonical_order=1,
        raw_order=1,
        content="Table",
        evidence_ids=["ev-tbl"],
        headers=["Year", "Rev"],
        rows=[["2022", "100"]]
    )
    num_el = CanonicalElement(
        element_id="el-num",
        type="paragraph",
        canonical_order=2,
        raw_order=2,
        content="Revenue was ₹500 million in FY2022",
        evidence_ids=["ev-num"]
    )
    cap_el = CanonicalElement(
        element_id="el-cap",
        type="caption",
        canonical_order=3,
        raw_order=3,
        content="Figure 1: Revenue by segment",
        evidence_ids=["ev-cap"]
    )
    fig_el = CanonicalFigure(
        element_id="fig-1",
        canonical_order=4,
        raw_order=4,
        content="Figure",
        evidence_ids=["ev-fig"],
        caption="Network growth"
    )

    assert calculate_candidate_priority(table) == 1
    assert calculate_candidate_priority(num_el) == 2
    assert calculate_candidate_priority(cap_el) == 5
    assert calculate_candidate_priority(fig_el) == 6

def test_select_candidates_filters_headers_footers():
    meta = DocumentMetadata(
        document_id="doc-test",
        filename="test.pdf",
        page_count=1,
        parser="docling",
        file_size_bytes=1000,
        sha256="abc",
        processing_status="success"
    )
    elements = [
        CanonicalElement(
            element_id="h-1",
            type="page_header",
            canonical_order=0,
            raw_order=0,
            content="DELHIVERY LIMITED PROSPECTUS",
            evidence_ids=["ev-h"]
        ),
        CanonicalElement(
            element_id="p-1",
            type="paragraph",
            canonical_order=1,
            raw_order=1,
            content="Delhivery operates 93 fulfilment centres covering 6.25 million square feet.",
            evidence_ids=["ev-p1"]
        ),
        CanonicalElement(
            element_id="f-1",
            type="page_footer",
            canonical_order=2,
            raw_order=2,
            content="Page 12",
            evidence_ids=["ev-f"]
        )
    ]
    page = CanonicalPage(pdf_page_number=1, elements=elements)
    doc = CanonicalDocument(document_id="doc-test", source_filename="test.pdf", metadata=meta, pages=[page])

    candidates = select_candidates(doc)
    candidate_ids = [c.element_id for c in candidates]
    
    assert "p-1" in candidate_ids
    assert "h-1" not in candidate_ids
    assert "f-1" not in candidate_ids
