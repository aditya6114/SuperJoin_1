import re
from typing import Optional, Dict

# Controlled vocabulary for canonical predicates
PREDICATE_REVENUE = "revenue"
PREDICATE_PROFIT = "profit"
PREDICATE_LOSS = "loss"
PREDICATE_EBITDA = "ebitda"
PREDICATE_GROWTH = "growth"
PREDICATE_DECLINE = "decline"
PREDICATE_MARGIN = "margin"
PREDICATE_EXPENDITURE = "expenditure"
PREDICATE_INCOME = "income"
PREDICATE_FLOOR_AREA = "floor_area"
PREDICATE_COUNT_OF = "count_of"
PREDICATE_EMPLOYEES = "employees"

PREDICATE_OPERATES = "operates"
PREDICATE_OWNS = "owns"
PREDICATE_ACQUIRED = "acquired"
PREDICATE_LAUNCHED = "launched"
PREDICATE_PROVIDES = "provides"
PREDICATE_SERVES = "serves"
PREDICATE_LOCATED_AT = "located_at"

PREDICATE_APPOINTED_AS = "appointed_as"
PREDICATE_RESIGNED_AS = "resigned_as"

# Verb / phrase mapping to canonical predicate
VERB_TO_PREDICATE = {
    r"\b(operates|operating|operated)\b": PREDICATE_OPERATES,
    r"\b(owns|owning|owned)\b": PREDICATE_OWNS,
    r"\b(acquired|acquiring|acquisition\s+of)\b": PREDICATE_ACQUIRED,
    r"\b(launched|launching)\b": PREDICATE_LAUNCHED,
    r"\b(provides|providing|provided)\b": PREDICATE_PROVIDES,
    r"\b(serves|serving|served)\b": PREDICATE_SERVES,
    r"\b(appointed\s+as|appointed\s+director|appointed|joined\s+as)\b": PREDICATE_APPOINTED_AS,
    r"\b(resigned\s+as|resigned|stepped\s+down\s+as)\b": PREDICATE_RESIGNED_AS,
    r"\b(located\s+at|headquartered\s+at|situated\s+at|address\s+is)\b": PREDICATE_LOCATED_AT,
    r"\b(covering|floor\s+area\s+of)\b": PREDICATE_FLOOR_AREA,
}

# Metric name mapping for table headers and text references
METRIC_TO_PREDICATE = {
    r"^revenue(\s+from\s+operations)?$": PREDICATE_REVENUE,
    r"^total\s+revenue$": PREDICATE_REVENUE,
    r"^net\s+profit$": PREDICATE_PROFIT,
    r"^pat$": PREDICATE_PROFIT,
    r"^profit$": PREDICATE_PROFIT,
    r"^net\s+loss$": PREDICATE_LOSS,
    r"^loss$": PREDICATE_LOSS,
    r"^ebitda$": PREDICATE_EBITDA,
    r"^adjusted\s+ebitda$": PREDICATE_EBITDA,
    r"^growth(\s*\(%\))?$": PREDICATE_GROWTH,
    r"^margin(\s*\(%\))?$": PREDICATE_MARGIN,
    r"^employees$": PREDICATE_EMPLOYEES,
    r"^headcount$": PREDICATE_EMPLOYEES,
}

def map_verb_to_predicate(phrase: str) -> Optional[str]:
    """Matches a surface verb/phrase to a canonical predicate."""
    phrase_clean = phrase.strip().lower()
    for pattern, canonical in VERB_TO_PREDICATE.items():
        if re.search(pattern, phrase_clean):
            return canonical
    return None

def map_metric_to_predicate(header_name: str) -> str:
    """Matches a table header or metric name to a canonical predicate or normalized label."""
    clean = header_name.strip().lower()
    for pattern, canonical in METRIC_TO_PREDICATE.items():
        if re.search(pattern, clean):
            return canonical
    # Fallback: snake_case alphanumeric representation
    sanitized = re.sub(r'[^a-z0-9]+', '_', clean).strip('_')
    return sanitized or "metric"
