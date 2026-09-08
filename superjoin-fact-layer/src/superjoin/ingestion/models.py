from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union


class BoundingBox(BaseModel):
    left: float
    top: float
    right: float
    bottom: float

class CanonicalElement(BaseModel):
    element_id: str
    type: str  # paragraph, section_header, list_item, table, figure/image, caption, footnote, page_header, page_footer, unknown
    canonical_order: int
    raw_order: int
    bbox: Optional[BoundingBox] = None
    content: str
    raw_content: Optional[str] = None
    evidence_ids: List[str]

class CanonicalTable(CanonicalElement):
    type: str = "table"
    caption: Optional[str] = None
    headers: List[str] = []
    rows: List[List[str]] = []
    source: Optional[str] = None

class CanonicalFigure(CanonicalElement):
    type: str = "figure"
    caption: Optional[str] = None
    image_reference: Optional[str] = None
    text_fragments: List[Dict[str, Any]] = []

class CanonicalPage(BaseModel):
    pdf_page_number: int
    printed_page_number: Optional[int] = None
    width: Optional[float] = None
    height: Optional[float] = None
    elements: List[Union[CanonicalTable, CanonicalFigure, CanonicalElement]]

class DocumentMetadata(BaseModel):
    document_id: str
    filename: str
    page_count: int
    parser: str
    parser_version: Optional[str] = None
    file_size_bytes: int
    sha256: str
    title: Optional[str] = None
    processing_status: str

class CanonicalDocument(BaseModel):
    document_id: str
    source_filename: str
    metadata: DocumentMetadata
    pages: List[CanonicalPage]
    warnings: List[str] = []

class RawParseResult(BaseModel):
    # Adapter for holding the raw docling objects without forcing downstream to import docling
    docling_document: Any
    metadata: DocumentMetadata
