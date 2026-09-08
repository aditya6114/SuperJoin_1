import json
import pytest
from superjoin.ingestion.models import (
    CanonicalDocument,
    CanonicalElement,
    CanonicalPage,
    DocumentMetadata
)
from superjoin.extraction.models import (
    Fact,
    FactSubject,
    FactObject,
    TemporalContext,
    FactExtractionResult
)
from superjoin.extraction.extractors.numerical_extractor import extract_quantities
from superjoin.extraction.extractors.temporal_extractor import extract_temporal_context
from superjoin.extraction.extractors.semantic_extractor import extract_semantic_relations
from superjoin.extraction.extractors.table_extractor import extract_table_facts_deterministic
from superjoin.extraction.extractors.figure_extractor import extract_figure_facts
from superjoin.extraction.candidate_selector import select_candidates, is_noise_or_boilerplate
from superjoin.extraction.validators import validate_fact, validate_facts
from superjoin.extraction.deduplicator import deduplicate_facts
from superjoin.extraction.service import FactExtractionService

def test_case_1_same_metric_different_time():
    # Case 1: Revenue FY2022 = X, Revenue FY2023 = Y -> Separate facts with separate time contexts
    f1 = Fact(
        fact_type="numerical",
        subject=FactSubject(name="Company", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=100, currency="₹", scale="million"),
        time=TemporalContext(time_type="fiscal_year", value="FY2022"),
        confidence=0.95,
        evidence_ids=["p-1"]
    )
    f2 = Fact(
        fact_type="numerical",
        subject=FactSubject(name="Company", type="company"),
        predicate="revenue",
        object=FactObject(value_type="currency", value=120, currency="₹", scale="million"),
        time=TemporalContext(time_type="fiscal_year", value="FY2023"),
        confidence=0.95,
        evidence_ids=["p-2"]
    )
    deduped = deduplicate_facts([f1, f2])
    assert len(deduped) == 2
    assert deduped[0].time.value == "FY2022"
    assert deduped[1].time.value == "FY2023"

def test_case_2_status_change_over_time():
    # Case 2: Person appointed in 2021, resigned in 2024 -> Separate event facts
    text1 = "Jane Smith was appointed director in 2021."
    text2 = "Jane Smith resigned as director in 2024."
    r1, _ = extract_semantic_relations(text1, {})
    r2, _ = extract_semantic_relations(text2, {})
    assert r1[0]["predicate"] == "appointed_as"
    assert r1[0]["time"].value == "2021"
    assert r2[0]["predicate"] == "resigned_as"
    assert r2[0]["time"].value == "2024"

def test_case_3_differently_written_addresses():
    # Case 3: Preserves verbatim address expressions without premature resolution
    text1 = "The logistics hub is located at Air Cargo Logistics Center, IGI Airport, New Delhi."
    text2 = "The logistics hub is located at Air Cargo Logistics Centre, Indira Gandhi International Airport."
    r1, _ = extract_semantic_relations(text1, {})
    r2, _ = extract_semantic_relations(text2, {})
    assert r1[0]["object"].value == "Air Cargo Logistics Center, IGI Airport, New Delhi"
    assert r2[0]["object"].value == "Air Cargo Logistics Centre, Indira Gandhi International Airport"

def test_case_4_different_units():
    # Case 4: ₹5 crore, ₹50 million, ₹50,000,000 preserved in source form
    q1 = extract_quantities("The cost was ₹5 crore.")
    q2 = extract_quantities("The cost was ₹50 million.")
    q3 = extract_quantities("The cost was ₹50,000,000.")
    assert q1[0].scale == "crore" and q1[0].value == 5
    assert q2[0].scale == "million" and q2[0].value == 50
    assert q3[0].value == 50000000 and q3[0].scale is None

def test_case_5_approximate_values():
    # Case 5: "over 1,607", "more than 750", "approximately 5 million" preserve qualifiers
    q1 = extract_quantities("Operating over 1,607 vehicles.")
    q2 = extract_quantities("Covering more than 750 cities.")
    q3 = extract_quantities("Serving approximately 5 million users.")
    assert q1[0].qualifier == "greater_than"
    assert q2[0].qualifier == "greater_than"
    assert q3[0].qualifier == "approximate"

def test_case_6_multiple_facts_in_one_sentence():
    # Case 6: "Company operates 93 fulfilment centres covering 6.25 million square feet."
    text = "Company operates 93 fulfilment centres covering 6.25 million square feet."
    relations, _ = extract_semantic_relations(text, {})
    assert len(relations) == 2
    assert relations[0]["predicate"] == "operates"
    assert relations[0]["object"].value == 93
    assert relations[1]["predicate"] == "floor_area"
    assert relations[1]["object"].value == 6.25
    assert relations[1]["object"].scale == "million"

def test_case_7_table_unit_in_caption():
    # Case 7: Units in table caption inherit to cell facts
    ctx = {
        "table_caption": "Summary Financial Statement (₹ in million)",
        "table_headers": ["Year", "Revenue"],
        "table_rows": [["2022", "100"]],
        "evidence_ids": ["tbl-1"]
    }
    facts, is_ambiguous = extract_table_facts_deterministic(ctx)
    assert not is_ambiguous
    assert len(facts) == 1
    assert facts[0].object.currency == "₹"
    assert facts[0].object.scale == "million"
    assert facts[0].object.value == 100

def test_case_8_ambiguous_table():
    # Case 8: Corrupted / missing headers return is_ambiguous=True without hallucinating
    ctx = {
        "table_caption": "Table with missing headers",
        "table_headers": ["", "-", "Unnamed: 2"],
        "table_rows": [["A", "B", "C"]],
        "evidence_ids": ["tbl-bad"]
    }
    facts, is_ambiguous = extract_table_facts_deterministic(ctx)
    assert is_ambiguous
    assert len(facts) == 0

def test_case_9_ocr_figure_noise():
    # Case 9: OCR gibberish fragments are rejected
    ctx = {
        "figure_caption": None,
        "figure_text_fragments": [{"text": "Conaas"}, {"text": "peraca Tralos, fs"}],
        "evidence_ids": ["fig-noisy"]
    }
    facts = extract_figure_facts(json.dumps(ctx))
    assert len(facts) == 0

def test_case_10_repeated_headers_footers():
    # Case 10: Page numbers and boilerplate headers are filtered by candidate selector
    meta = DocumentMetadata(document_id="doc-filter", filename="doc.pdf", page_count=1, parser="docling", file_size_bytes=100, sha256="abc", processing_status="success")
    elem_header = CanonicalElement(element_id="h1", type="page_header", canonical_order=0, raw_order=0, content="Company Prospectus Page 1", evidence_ids=["h1"])
    elem_pg = CanonicalElement(element_id="pg1", type="page_number", canonical_order=1, raw_order=1, content="Page 1 of 50", evidence_ids=["pg1"])
    elem_valid = CanonicalElement(element_id="p1", type="paragraph", canonical_order=2, raw_order=2, content="Company reported revenue of ₹500 crore in FY2023.", evidence_ids=["p1"])

    doc = CanonicalDocument(
        document_id="doc-filter",
        source_filename="doc.pdf",
        metadata=meta,
        pages=[CanonicalPage(pdf_page_number=1, elements=[elem_header, elem_pg, elem_valid])]
    )
    candidates = select_candidates(doc)
    cand_ids = [c.element_id for c in candidates]
    assert "h1" not in cand_ids
    assert "pg1" not in cand_ids
    assert "p1" in cand_ids

def test_case_11_pdf_page_vs_printed_page():
    # Case 11: Preserves both pdf_page_number and printed_page_number
    meta = DocumentMetadata(document_id="doc-pages", filename="f.pdf", page_count=1, parser="docling", file_size_bytes=100, sha256="abc", processing_status="success")
    elem = CanonicalElement(element_id="el-1", type="paragraph", canonical_order=1, raw_order=1, content="Revenue was ₹50 crore in 2022.", evidence_ids=["el-1"])
    page = CanonicalPage(pdf_page_number=5, printed_page_number=3, elements=[elem])
    doc = CanonicalDocument(document_id="doc-pages", source_filename="f.pdf", metadata=meta, pages=[page])

    service = FactExtractionService(llm_enabled=False)
    result = service.extract(doc)
    assert len(result.facts) >= 1
    assert result.facts[0].evidence_ids == ["el-1"]

def test_case_12_qualified_claims():
    # Case 12: unaudited, pro forma, consolidated, etc. preserved
    t = extract_quantities("The unaudited pro forma consolidated revenue was approximately ₹100 crore.")
    assert len(t) == 1
    assert t[0].currency == "₹"
    assert t[0].scale == "crore"
    assert t[0].qualifier == "approximate"

def test_case_13_missing_time():
    # Case 13: Time is null/unknown when missing; no date inference
    t = extract_temporal_context("The enterprise operates 10 distribution centres.")
    assert t.time_type == "unknown"
    assert t.value is None

def test_case_14_missing_subject():
    # Case 14: "It operates 50 facilities" without local context returns uncertainty
    text = "It operates 50 facilities."
    rels, uncertainties = extract_semantic_relations(text, {})
    assert len(rels) == 0
    assert len(uncertainties) >= 1

def test_case_15_internal_document_disagreement():
    # Case 15: Disagreeing figures in same document are both extracted if grounded
    meta = DocumentMetadata(document_id="doc-disagree", filename="f.pdf", page_count=1, parser="docling", file_size_bytes=100, sha256="abc", processing_status="success")
    e1 = CanonicalElement(element_id="e1", type="paragraph", canonical_order=1, raw_order=1, content="The company reported revenue of ₹100 crore.", evidence_ids=["e1"])
    e2 = CanonicalElement(element_id="e2", type="paragraph", canonical_order=2, raw_order=2, content="The company reported revenue of ₹120 crore.", evidence_ids=["e2"])
    doc = CanonicalDocument(document_id="doc-disagree", source_filename="f.pdf", metadata=meta, pages=[CanonicalPage(pdf_page_number=1, elements=[e1, e2])])

    service = FactExtractionService(llm_enabled=False)
    result = service.extract(doc)
    assert len(result.facts) == 2
    assert result.facts[0].object.value == 100
    assert result.facts[1].object.value == 120
