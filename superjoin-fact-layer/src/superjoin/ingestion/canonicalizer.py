from typing import List, Dict, Optional, Any
from docling.datamodel.document import TableItem, TextItem, PictureItem
from .models import (
    CanonicalDocument, CanonicalPage, CanonicalElement,
    CanonicalTable, CanonicalFigure, BoundingBox, RawParseResult
)
import re

class TextNormalizer:
    @staticmethod
    def normalize(text: str) -> str:
        if not text:
            return ""
        # Remove control characters like \u0007
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        # Normalize repeated whitespace
        text = re.sub(r'[ \t]+', ' ', text)
        # Fix bullet artifacts like "• " -> "• "
        text = text.replace('•  ', '• ')
        return text.strip()

class TableNormalizer:
    @staticmethod
    def normalize(headers: List[str], rows: List[List[str]]) -> tuple[Optional[str], List[str], List[List[str]], Optional[str]]:
        caption = None
        source = None
        
        # Check if first header contains a table caption, e.g. "Table IV.1: Onion and tomato crop calendar.Vegetable"
        if headers and len(headers) > 0:
            first_header = headers[0]
            # Adjust regex to capture "Table X.Y: Caption" and leaving the rest for the header
            match = re.match(r'^(Table[\s\w\.]+:[^\.]+)\.(.*)$', first_header)
            if match:
                caption = match.group(1).strip()
                headers[0] = match.group(2).strip()

        # Check for source rows
        # If any row is purely "Source: ..." merged across cells
        new_rows = []
        for row in rows:
            joined_row = " ".join([str(cell).strip() for cell in row if str(cell).strip()])
            if joined_row.lower().startswith("source:"):
                source = joined_row
            else:
                new_rows.append(row)
                
        return caption, headers, new_rows, source

class ReadingOrderResolver:
    @staticmethod
    def resolve(elements: List[CanonicalElement]) -> List[CanonicalElement]:
        # Sort elements by top coordinate, handling basic column inference
        def get_sort_key(el: CanonicalElement):
            if not el.bbox:
                return (0, 0)
            
            # Simple heuristic: cluster X into rough columns (e.g., 200px wide bins)
            # This prevents right column text from interleaving with left column text
            col_x = round(el.bbox.left / 250) * 250
            return (col_x, el.bbox.top)

        elements.sort(key=get_sort_key)
        
        for i, el in enumerate(elements):
            el.canonical_order = i
            
        return elements

class Canonicalizer:
    def canonicalize(self, raw_result: RawParseResult) -> CanonicalDocument:
        docling_doc = raw_result.docling_document
        metadata = raw_result.metadata
        
        pages_dict: Dict[int, CanonicalPage] = {}
        
        if hasattr(docling_doc, 'pages'):
            for page_no, page_info in docling_doc.pages.items():
                pages_dict[page_no] = CanonicalPage(
                    pdf_page_number=page_no,
                    printed_page_number=None,
                    width=page_info.size.width if page_info.size else None,
                    height=page_info.size.height if page_info.size else None,
                    elements=[]
                )
            
        # Docling 2.0 iterate items
        items = getattr(docling_doc, 'texts', []) + getattr(docling_doc, 'tables', []) + getattr(docling_doc, 'pictures', [])
        
        page_elements: Dict[int, List[CanonicalElement]] = {p: [] for p in pages_dict}
        
        order_idx = 0
        for item in items:
            page_no = item.prov[0].page_no if hasattr(item, 'prov') and item.prov and len(item.prov) > 0 else 1
            if page_no not in pages_dict:
                pages_dict[page_no] = CanonicalPage(pdf_page_number=page_no, elements=[])
                page_elements[page_no] = []
                
            bbox = None
            if hasattr(item, 'prov') and item.prov and len(item.prov) > 0 and item.prov[0].bbox:
                pb = item.prov[0].bbox
                bbox = BoundingBox(left=pb.l, top=pb.t, right=pb.r, bottom=pb.b)
                
            block_type = getattr(item, 'label', 'unknown')
            if isinstance(item, TableItem):
                block_type = 'table'
            elif isinstance(item, PictureItem):
                block_type = 'figure'
                
            element_id = f"{metadata.document_id}:p{page_no}:e{order_idx}"
            evidence_ids = [f"{metadata.document_id}:p{page_no}:b{order_idx}"]
            
            if isinstance(item, TableItem):
                raw_text = ""
                headers = []
                rows = []
                if hasattr(item, 'export_to_dataframe'):
                    try:
                        df = item.export_to_dataframe()
                        headers = [str(c) for c in df.columns]
                        rows = [[str(cell) for cell in row] for row in df.values.tolist()]
                    except Exception:
                        pass
                
                caption, headers, rows, source = TableNormalizer.normalize(headers, rows)
                
                el = CanonicalTable(
                    element_id=element_id,
                    type=block_type,
                    canonical_order=0,
                    raw_order=order_idx,
                    bbox=bbox,
                    content="",
                    raw_content=raw_text,
                    evidence_ids=evidence_ids,
                    caption=caption,
                    headers=headers,
                    rows=rows,
                    source=source
                )
            elif isinstance(item, PictureItem):
                el = CanonicalFigure(
                    element_id=element_id,
                    type=block_type,
                    canonical_order=0,
                    raw_order=order_idx,
                    bbox=bbox,
                    content="",
                    evidence_ids=evidence_ids,
                    caption=None,
                    image_reference=None,
                    text_fragments=[]
                )
            else:
                raw_text = getattr(item, 'text', '')
                normalized_text = TextNormalizer.normalize(raw_text)
                
                # Extract printed page number
                if block_type in ['page_header', 'page_footer'] and pages_dict[page_no].printed_page_number is None:
                    match = re.search(r'\b\d+\b', normalized_text)
                    if match:
                        pages_dict[page_no].printed_page_number = int(match.group())

                el = CanonicalElement(
                    element_id=element_id,
                    type=block_type,
                    canonical_order=0,
                    raw_order=order_idx,
                    bbox=bbox,
                    content=normalized_text,
                    raw_content=raw_text,
                    evidence_ids=evidence_ids
                )
                
            page_elements[page_no].append(el)
            order_idx += 1
            
        # Resolve reading order per page
        for page_no, elements in page_elements.items():
            resolved_elements = ReadingOrderResolver.resolve(elements)
            pages_dict[page_no].elements = resolved_elements
            
        pages_list = [pages_dict[k] for k in sorted(pages_dict.keys())]
        
        return CanonicalDocument(
            document_id=metadata.document_id,
            source_filename=metadata.filename,
            metadata=metadata,
            pages=pages_list,
            warnings=[]
        )
