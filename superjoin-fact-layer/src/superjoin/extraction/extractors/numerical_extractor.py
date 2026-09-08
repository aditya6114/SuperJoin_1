import re
from typing import List, Optional, Tuple
from ..models import FactObject
from ..rules.qualifiers import get_comparison_qualifier
from ..rules.patterns import CURRENCY_MAP, SCALE_MAP

def _parse_numeric_value(raw: str) -> int | float:
    """Parses a string number with commas into an int or float."""
    clean = raw.replace(',', '').strip()
    if '.' in clean:
        return float(clean)
    return int(clean)

QUANTITY_REGEX = re.compile(
    r'(?:(?P<qualifier>over|more\s+than|greater\s+than|less\s+than|approximately|approx\.|about|around|nearly|at\s+least|up\s+to)\s+)?'
    r'(?:(?P<currency>₹|INR|Rs\.?|\$|USD|€|EUR|£|GBP)\s*)?'
    r'(?P<number>[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|[-+]?\d+(?:\.\d+)?)'
    r'(?:\s*(?P<scale>million|billion|crore|crores|lakh|lakhs|thousand|thousands|trillion)\b)?'
    r'(?:\s*(?P<unit>%|percent|square\s*feet|sq\.?\s*ft\.?|sqft|tonnes|metric\s*tonnes|guards|centres|centers|facilities|employees|km|mt))?',
    re.IGNORECASE
)

def extract_quantities(text: str) -> List[FactObject]:
    """
    Extracts structured quantities (numbers, currencies, percentages, units, scales, qualifiers)
    from text, preserving source semantics without lossy standard unit normalization.
    """
    if not text:
        return []

    quantities: List[FactObject] = []
    seen_spans = set()

    for match in QUANTITY_REGEX.finditer(text):
        span = match.span()
        if any(s <= span[0] and span[1] <= e for s, e in seen_spans):
            continue

        raw_qualifier = match.group("qualifier")
        raw_currency = match.group("currency")
        raw_number = match.group("number")
        raw_scale = match.group("scale")
        raw_unit = match.group("unit")

        if not raw_number:
            continue

        # Must have at least a currency, scale, unit, or qualifier, or be a standalone number in context
        if not (raw_currency or raw_scale or raw_unit or raw_qualifier):
            # Standalone number: skip 4-digit years (handled by temporal extractor)
            if len(raw_number) == 4 and (raw_number.startswith("19") or raw_number.startswith("20")):
                continue

        try:
            val = _parse_numeric_value(raw_number)
        except (ValueError, AttributeError):
            continue

        seen_spans.add(span)

        # Determine qualifier
        qualifier = None
        if raw_qualifier:
            qualifier = get_comparison_qualifier(raw_qualifier)

        # Determine currency
        currency = None
        if raw_currency:
            currency = CURRENCY_MAP.get(raw_currency.lower(), raw_currency.upper())

        # Determine scale
        scale = None
        if raw_scale:
            scale = SCALE_MAP.get(raw_scale.lower(), raw_scale.lower())

        # Determine unit and value_type
        unit = None
        value_type = "number"

        if raw_unit:
            u_clean = raw_unit.lower()
            if u_clean in ("%", "percent"):
                value_type = "percentage"
                unit = "%"
            else:
                value_type = "quantity"
                unit = raw_unit.strip().rstrip('.')
        elif currency:
            value_type = "currency"
        elif scale:
            value_type = "number"
        elif qualifier:
            value_type = "quantity"

        quantities.append(FactObject(
            value_type=value_type,
            value=val,
            unit=unit,
            currency=currency,
            scale=scale,
            qualifier=qualifier
        ))

    return quantities
