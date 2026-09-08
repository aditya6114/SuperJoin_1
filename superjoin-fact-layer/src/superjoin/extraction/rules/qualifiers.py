import re
from typing import List, Tuple, Optional

QUALIFIER_PATTERNS = [
    # Approximation
    (r"\bapproximately\b", "approximately"),
    (r"\babout\b", "about"),
    (r"\baround\b", "around"),
    (r"\bnearly\b", "nearly"),
    (r"\bestimated\b", "estimated"),
    
    # Comparison
    (r"\bover\b", "over"),
    (r"\bmore\s+than\b", "more than"),
    (r"\bat\s+least\b", "at least"),
    (r"\bup\s+to\b", "up to"),
    (r"\bless\s+than\b", "less than"),

    # Accounting & Scope
    (r"\bunaudited\b", "unaudited"),
    (r"\bpro\s*forma\b", "pro forma"),
    (r"\bconsolidated\b", "consolidated"),
    (r"\bstandalone\b", "standalone"),
    (r"\bincluding\b", "including"),
    (r"\bexcluding\b", "excluding"),
    (r"\bcontinuing\s+operations\b", "continuing operations"),
    (r"\bconstant\s+currency\b", "constant currency"),

    # Temporal context markers preserved as qualifiers
    (r"\bas\s+of\b", "as of"),
    (r"\bduring\b", "during"),
    (r"\bfor\s+the\s+year\s+ended\b", "for the year ended"),
]

COMPILED_QUALIFIERS = [
    (re.compile(pat, re.IGNORECASE), canonical)
    for pat, canonical in QUALIFIER_PATTERNS
]

def extract_qualifiers(text: str) -> List[str]:
    """Identifies and returns all explicit qualifiers present in the text."""
    if not text:
        return []
    qualifiers: List[str] = []
    for pattern, canonical in COMPILED_QUALIFIERS:
        if pattern.search(text):
            if canonical not in qualifiers:
                qualifiers.append(canonical)
    return qualifiers

def get_comparison_qualifier(text: str) -> Optional[str]:
    """Returns normalized comparison operator if present."""
    lower = text.lower()
    if re.search(r'\b(over|more\s+than|greater\s+than)\b', lower):
        return "greater_than"
    if re.search(r'\b(less\s+than|under)\b', lower):
        return "less_than"
    if re.search(r'\b(at\s+least)\b', lower):
        return "greater_than_or_equal"
    if re.search(r'\b(up\s+to|at\s+most)\b', lower):
        return "less_than_or_equal"
    if re.search(r'\b(approximately|approx\.|about|around|nearly)\b', lower):
        return "approximate"
    return None
