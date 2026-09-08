import json
from typing import Dict, Any, List
from superjoin.ingestion.models import (
    CanonicalDocument,
    CanonicalElement,
    CanonicalTable,
    CanonicalFigure
)

def find_section_hierarchy(document: CanonicalDocument, target_order: int) -> List[str]:
    """Finds the chain of preceding section headers before the target element."""
    headers: List[str] = []
    for page in document.pages:
        for el in page.elements:
            if el.canonical_order >= target_order:
                return headers[-3:]  # return up to 3 most recent headers for hierarchy
            if el.type == "section_header" and el.content.strip():
                headers.append(el.content.strip())
    return headers[-3:]

def build_context(document: CanonicalDocument, candidate: CanonicalElement) -> str:
    """Builds a localized, targeted context string for the LLM."""
    
    # Base context
    context_data: Dict[str, Any] = {
        "document_id": document.metadata.document_id,
        "document_title": document.metadata.title,
        "element_id": candidate.element_id,
        "element_type": candidate.type,
        "evidence_ids": candidate.evidence_ids,
        "pdf_page_number": None,
        "printed_page_number": None,
    }
    
    # Find page number
    for page in document.pages:
        if any(e.element_id == candidate.element_id for e in page.elements):
            context_data["pdf_page_number"] = page.pdf_page_number
            context_data["printed_page_number"] = page.printed_page_number
            break
            
    # Add section hierarchy
    hierarchy = find_section_hierarchy(document, candidate.canonical_order)
    if hierarchy:
        context_data["section_hierarchy"] = hierarchy
        context_data["preceding_section_header"] = hierarchy[-1]

    # Specific context based on element type
    if candidate.type == "table":
        context_data["table_caption"] = getattr(candidate, "caption", None)
        context_data["table_headers"] = getattr(candidate, "headers", [])
        context_data["table_rows"] = getattr(candidate, "rows", [])
        context_data["table_source"] = getattr(candidate, "source", None)
    elif candidate.type in ("figure", "image"):
        context_data["figure_caption"] = getattr(candidate, "caption", None)
        context_data["figure_text_fragments"] = getattr(candidate, "text_fragments", [])
    else:
        # Text element: paragraph, list_item, section_header, caption, footnote
        context_data["content"] = candidate.content
        
        # Add adjacent surrounding elements for context resolution (e.g. subject/time reference)
        surrounding = []
        for page in document.pages:
            for el in page.elements:
                if 0 < abs(el.canonical_order - candidate.canonical_order) <= 2:
                    if el.type in ("paragraph", "text", "list_item", "caption", "section_header"):
                        surrounding.append({
                            "element_id": el.element_id,
                            "type": el.type,
                            "content": el.content,
                            "evidence_ids": el.evidence_ids
                        })
        if surrounding:
            context_data["surrounding_elements"] = surrounding
            
    return json.dumps(context_data, indent=2)
