import re
from typing import List, Set
from superjoin.ingestion.models import (
    CanonicalDocument, 
    CanonicalElement, 
    CanonicalTable, 
    CanonicalFigure
)

BOILERPLATE_PATTERNS = [
    re.compile(r'table\s+of\s+contents', re.IGNORECASE),
    re.compile(r'all\s+rights\s+reserved', re.IGNORECASE),
    re.compile(r'strictly\s+private\s+and\s+confidential', re.IGNORECASE),
    re.compile(r'this\s+page\s+(is\s+)?intentionally\s+left\s+blank', re.IGNORECASE),
    re.compile(r'^\s*page\s+\d+(\s+of\s+\d+)?\s*$', re.IGNORECASE),
    re.compile(r'^\s*-\s*\d+\s*-\s*$', re.IGNORECASE),
]

def is_table_element(element: CanonicalElement) -> bool:
    """Checks if an element represents a table, inspecting element.type and table properties."""
    return element.type == "table"

def is_figure_element(element: CanonicalElement) -> bool:
    """Checks if an element represents a figure or image."""
    return element.type in ("figure", "image")

def is_noise_or_boilerplate(text: str) -> bool:
    """Detects repeated headers/footers, TOC, page numbers, or legal boilerplate."""
    if not text or len(text.strip()) < 3:
        return True
    
    clean = text.strip()
    for pattern in BOILERPLATE_PATTERNS:
        if pattern.search(clean):
            return True
            
    # Check for obvious OCR garbage (low alphanumeric ratio)
    alnum_count = sum(1 for c in clean if c.isalnum())
    if len(clean) > 8 and (alnum_count / len(clean)) < 0.35:
        return True
        
    return False

def contains_numeric_signal(text: str) -> bool:
    """Check for numbers, currencies, percentages, scales."""
    pattern = re.compile(
        r'(\$|₹|€|£|INR|USD)?\s*\d+([.,]\d+)?\s*(%|percent|million|billion|crore|lakh|thousand|centres|centers|sq\s*ft|square\s*feet|mt|km)?',
        re.IGNORECASE
    )
    return bool(pattern.search(text))

def contains_temporal_signal(text: str) -> bool:
    """Check for years, months, quarters, fiscal years, or dates."""
    pattern = re.compile(
        r'(FY\s*\d{2,4}|20\d{2}|19\d{2}|Q[1-4]\s*(FY)?\s*\d{0,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{2,4}|year\s+ended|as\s+of|during\s+the\s+year|since\s+\d{4})',
        re.IGNORECASE
    )
    return bool(pattern.search(text))

def contains_fact_predicate(text: str) -> bool:
    """Check for common business, financial, operational, or event predicates."""
    keywords = [
        "revenue", "profit", "loss", "operates", "operated", "operating",
        "acquired", "acquisition", "resigned", "appointed", "joined",
        "employees", "headcount", "growth", "margin", "owns", "owned",
        "located", "facility", "facilities", "fulfilment", "fulfillment",
        "ebitda", "ebit", "income", "expense", "expenditure", "market share",
        "volume", "sq ft", "square feet", "certified", "certification",
        "contract", "partnered", "founded", "headquartered"
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)

def is_fact_bearing_text(element: CanonicalElement) -> bool:
    """Check if a paragraph/text element likely contains facts."""
    if element.type in ("page_header", "page_footer", "page_number", "unknown"):
        return False
        
    text = element.content or ""
    if is_noise_or_boilerplate(text):
        return False
        
    # Element types that can bear facts
    if element.type in ("paragraph", "text", "list_item", "section_header", "footnote", "caption"):
        has_numeric = contains_numeric_signal(text)
        has_temporal = contains_temporal_signal(text)
        has_predicate = contains_fact_predicate(text)
        
        return has_predicate or (has_numeric and has_temporal) or has_numeric or (element.type == "caption")
        
    return False

def is_relevant_table(table: CanonicalTable) -> bool:
    """Check if a table contains data rather than just empty/layout rows."""
    rows = getattr(table, "rows", None)
    if not rows:
        return False
    # Avoid tables that are just single cells used for layout
    if len(rows) == 1 and len(rows[0]) <= 1:
        return False
    # Check if there is any text in the table
    has_any_content = any(any(str(cell).strip() for cell in row) for row in rows)
    return has_any_content

def is_relevant_figure(figure: CanonicalFigure) -> bool:
    """Check if a figure contains usable fragments or a meaningful caption."""
    caption = getattr(figure, "caption", None)
    text_fragments = getattr(figure, "text_fragments", None)
    if caption and not is_noise_or_boilerplate(caption):
        return True
    if text_fragments:
        valid_fragments = [
            f for f in text_fragments 
            if isinstance(f, dict) and f.get("text") and not is_noise_or_boilerplate(f.get("text", ""))
        ]
        if valid_fragments:
            return True
    return False

def calculate_candidate_priority(element: CanonicalElement) -> int:
    """
    Assigns candidate priority (lower number = higher priority).
    Order of priority:
    1. tables
    2. numerical text
    3. temporal text
    4. meaningful event/property statements
    5. captions
    6. relevant figure fragments
    """
    if is_table_element(element):
        return 1
        
    if is_figure_element(element):
        return 6
        
    if element.type == "caption":
        return 5
        
    text = element.content or ""
    has_num = contains_numeric_signal(text)
    has_time = contains_temporal_signal(text)
    has_pred = contains_fact_predicate(text)
    
    if has_num:
        return 2
    if has_time:
        return 3
    if has_pred:
        return 4
        
    return 10

def select_candidates(document: CanonicalDocument) -> List[CanonicalElement]:
    """Applies heuristics to return a prioritized list of candidates."""
    candidates = []
    seen_ids: Set[str] = set()
    
    for page in document.pages:
        for element in page.elements:
            if element.element_id in seen_ids:
                continue
                
            if is_table_element(element):
                if is_relevant_table(element):
                    candidates.append(element)
                    seen_ids.add(element.element_id)
            elif is_figure_element(element):
                if is_relevant_figure(element):
                    candidates.append(element)
                    seen_ids.add(element.element_id)
            else:
                if is_fact_bearing_text(element):
                    candidates.append(element)
                    seen_ids.add(element.element_id)
                    
    # Sort by priority first, then preserve canonical order
    candidates.sort(key=lambda x: (calculate_candidate_priority(x), x.canonical_order))
    return candidates
