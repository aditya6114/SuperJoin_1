import pytest
from superjoin.ingestion.canonicalizer import TextNormalizer, TableNormalizer, ReadingOrderResolver
from superjoin.ingestion.models import CanonicalElement, BoundingBox

def test_text_normalizer():
    # TEST 2 - Control character cleanup
    raw = "• \u0007 Sale of..."
    normalized = TextNormalizer.normalize(raw)
    assert normalized == "• Sale of..."
    
    # Bullet artifact fix
    assert TextNormalizer.normalize("•  Item") == "• Item"
    
    # Repeated whitespace
    assert TextNormalizer.normalize("Too   many spaces") == "Too many spaces"

def test_table_normalizer_caption_extraction():
    # TEST 3 - Table caption/header cleanup
    headers = ["Table IV.1: Onion and tomato crop calendar.Vegetable", "2023", "2024"]
    rows = [["Onion", "10", "20"]]
    
    caption, new_headers, new_rows, source = TableNormalizer.normalize(headers, rows)
    
    assert caption == "Table IV.1: Onion and tomato crop calendar"
    assert new_headers[0] == "Vegetable"
    assert new_headers[1] == "2023"

def test_table_normalizer_source_extraction():
    # TEST 4 - Table source extraction
    headers = ["Col1", "Col2"]
    rows = [
        ["Data1", "Data2"],
        ["Source: PIB releases", ""]
    ]
    
    caption, new_headers, new_rows, source = TableNormalizer.normalize(headers, rows)
    
    assert source == "Source: PIB releases"
    assert len(new_rows) == 1
    assert new_rows[0] == ["Data1", "Data2"]

def test_reading_order_resolver():
    # TEST 1 & TEST 9 - Multi-column reading order
    
    # Elements intentionally out of order
    e1 = CanonicalElement(
        element_id="e1", type="text", canonical_order=0, raw_order=0,
        content="Right col top", evidence_ids=[],
        bbox=BoundingBox(left=500, top=100, right=600, bottom=200)
    )
    e2 = CanonicalElement(
        element_id="e2", type="text", canonical_order=0, raw_order=1,
        content="Left col top", evidence_ids=[],
        bbox=BoundingBox(left=100, top=100, right=200, bottom=200)
    )
    e3 = CanonicalElement(
        element_id="e3", type="text", canonical_order=0, raw_order=2,
        content="Left col bottom", evidence_ids=[],
        bbox=BoundingBox(left=100, top=300, right=200, bottom=400)
    )
    
    elements = [e1, e2, e3]
    resolved = ReadingOrderResolver.resolve(elements)
    
    # Expected: e2 (left top), e3 (left bottom), e1 (right top)
    assert resolved[0].element_id == "e2"
    assert resolved[1].element_id == "e3"
    assert resolved[2].element_id == "e1"
