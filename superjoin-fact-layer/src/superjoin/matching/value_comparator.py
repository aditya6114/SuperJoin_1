import re
import math
from typing import Optional, List, Tuple
from pydantic import BaseModel
from superjoin.extraction.models import FactObject

# Multipliers for numerical scales
SCALE_MULTIPLIERS = {
    "thousand": 1e3,
    "k": 1e3,
    "lakh": 1e5,
    "lakhs": 1e5,
    "lac": 1e5,
    "lacs": 1e5,
    "million": 1e6,
    "mn": 1e6,
    "m": 1e6,
    "crore": 1e7,
    "crores": 1e7,
    "cr": 1e7,
    "crs": 1e7,
    "billion": 1e9,
    "bn": 1e9,
    "b": 1e9,
    "trillion": 1e12,
    "tn": 1e12,
    "t": 1e12,
}

# Currency normalization
CURRENCY_MAP = {
    "₹": "INR",
    "inr": "INR",
    "rs": "INR",
    "rs.": "INR",
    "rupee": "INR",
    "rupees": "INR",
    "$": "USD",
    "usd": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "€": "EUR",
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "£": "GBP",
    "gbp": "GBP",
    "pound": "GBP",
    "pounds": "GBP",
}

# Unit standardizations
UNIT_MAP = {
    "sq ft": "sq_ft",
    "sq. ft.": "sq_ft",
    "sqft": "sq_ft",
    "square feet": "sq_ft",
    "square foot": "sq_ft",
    "centres": "centres",
    "centers": "centres",
    "centre": "centres",
    "center": "centres",
    "fulfilment centres": "centres",
    "fulfilment centers": "centres",
    "fulfillment centres": "centres",
    "fulfillment centers": "centres",
    "facility": "facilities",
    "facilities": "facilities",
    "km": "km",
    "kms": "km",
    "kilometres": "km",
    "kilometers": "km",
    "tonne": "tonne",
    "tonnes": "tonne",
    "tons": "tonne",
    "ton": "tonne",
}


def normalize_currency(curr: Optional[str]) -> Optional[str]:
    if not curr:
        return None
    c = curr.strip().lower()
    return CURRENCY_MAP.get(c, curr.strip().upper())


def normalize_unit(unit: Optional[str]) -> Optional[str]:
    if not unit:
        return None
    u = unit.strip().lower()
    return UNIT_MAP.get(u, u)


def get_scale_multiplier(scale: Optional[str]) -> float:
    if not scale:
        return 1.0
    s = scale.strip().lower()
    return SCALE_MULTIPLIERS.get(s, 1.0)


def parse_numeric(val: any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = re.sub(r"[^\d.-]", "", val)
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    return None


def get_effective_qualifier(obj: FactObject, fact_qualifiers: Optional[List[str]]) -> Optional[str]:
    """Extract qualifier indicating bound or approximation."""
    if obj.qualifier:
        q = obj.qualifier.strip().lower()
        if q in {"approximate", "approximately", "around", "about"}:
            return "approximate"
        if q in {"greater_than", "over", "more_than", "at_least", "above"}:
            return "greater_than"
        if q in {"less_than", "under", "below", "at_most"}:
            return "less_than"
        return q

    if fact_qualifiers:
        for q_item in fact_qualifiers:
            q = q_item.strip().lower()
            if q in {"approximate", "approximately", "around", "about"}:
                return "approximate"
            if q in {"greater_than", "over", "more_than", "at_least", "above"}:
                return "greater_than"
            if q in {"less_than", "under", "below", "at_most"}:
                return "less_than"
    return None


class ValueComparisonResult(BaseModel):
    value_status: str  # "equal", "equivalent", "different", "compatible", "unknown", "not_applicable"
    unit_status: str   # "same", "converted", "different", "missing", "not_applicable"
    details: str
    normalized_value_a: Optional[float] = None
    normalized_value_b: Optional[float] = None


class ValueComparator:
    """Deterministic comparator for fact values, units, currencies, and qualifiers."""

    def __init__(self, approx_tolerance: float = 0.05):
        self.approx_tolerance = approx_tolerance

    def compare(
        self,
        obj_a: FactObject,
        obj_b: FactObject,
        qualifiers_a: Optional[List[str]] = None,
        qualifiers_b: Optional[List[str]] = None
    ) -> ValueComparisonResult:
        if not obj_a or not obj_b:
            return ValueComparisonResult(
                value_status="unknown",
                unit_status="unknown",
                details="Missing fact value object."
            )

        numeric_types = {"number", "percentage", "currency", "quantity"}
        is_num_a = obj_a.value_type in numeric_types
        is_num_b = obj_b.value_type in numeric_types

        if is_num_a and is_num_b:
            return self._compare_numeric(obj_a, obj_b, qualifiers_a, qualifiers_b)

        # Boolean comparison
        if obj_a.value_type == "boolean" and obj_b.value_type == "boolean":
            val_a = bool(obj_a.value)
            val_b = bool(obj_b.value)
            return ValueComparisonResult(
                value_status="equal" if val_a == val_b else "different",
                unit_status="not_applicable",
                details=f"Boolean values: {val_a} vs {val_b}"
            )

        # Textual / entity comparison
        val_a_str = str(obj_a.value).strip().lower() if obj_a.value is not None else ""
        val_b_str = str(obj_b.value).strip().lower() if obj_b.value is not None else ""

        if not val_a_str or not val_b_str:
            return ValueComparisonResult(
                value_status="unknown",
                unit_status="not_applicable",
                details="Empty or missing textual value."
            )

        if val_a_str == val_b_str:
            return ValueComparisonResult(
                value_status="equal",
                unit_status="not_applicable",
                details=f"Identical text values: '{obj_a.value}'"
            )

        return ValueComparisonResult(
            value_status="different",
            unit_status="not_applicable",
            details=f"Different text values: '{obj_a.value}' vs '{obj_b.value}'"
        )

    def _compare_numeric(
        self,
        obj_a: FactObject,
        obj_b: FactObject,
        qualifiers_a: Optional[List[str]],
        qualifiers_b: Optional[List[str]]
    ) -> ValueComparisonResult:
        raw_num_a = parse_numeric(obj_a.value)
        raw_num_b = parse_numeric(obj_b.value)

        if raw_num_a is None or raw_num_b is None:
            return ValueComparisonResult(
                value_status="unknown",
                unit_status="unknown",
                details="Could not parse numerical values."
            )

        # Currency check
        curr_a = normalize_currency(obj_a.currency)
        curr_b = normalize_currency(obj_b.currency)
        if curr_a and curr_b and curr_a != curr_b:
            return ValueComparisonResult(
                value_status="different",
                unit_status="different",
                details=f"Incompatible currencies: {curr_a} vs {curr_b}",
                normalized_value_a=raw_num_a,
                normalized_value_b=raw_num_b
            )

        # Unit check
        unit_a = normalize_unit(obj_a.unit)
        unit_b = normalize_unit(obj_b.unit)
        unit_status = "same"
        if unit_a and unit_b and unit_a != unit_b:
            return ValueComparisonResult(
                value_status="different",
                unit_status="different",
                details=f"Incompatible units: {unit_a} vs {unit_b}",
                normalized_value_a=raw_num_a,
                normalized_value_b=raw_num_b
            )
        elif bool(unit_a) != bool(unit_b):
            unit_status = "missing"
        elif not unit_a and not unit_b:
            unit_status = "not_applicable"

        # Percentage handling (e.g. 5% vs 0.05)
        # If one is percentage with value 5 and the other is number with value 0.05:
        mult_a = get_scale_multiplier(obj_a.scale)
        mult_b = get_scale_multiplier(obj_b.scale)

        base_a = raw_num_a * mult_a
        base_b = raw_num_b * mult_b

        is_pct_a = obj_a.value_type == "percentage"
        is_pct_b = obj_b.value_type == "percentage"

        if is_pct_a != is_pct_b:
            # One is percentage, one is number
            if is_pct_a and not is_pct_b:
                if math.isclose(base_a / 100.0, base_b, rel_tol=1e-5, abs_tol=1e-7):
                    return ValueComparisonResult(
                        value_status="equivalent",
                        unit_status="converted",
                        details=f"Percentage equivalence: {base_a}% == {base_b}",
                        normalized_value_a=base_a / 100.0,
                        normalized_value_b=base_b
                    )
            elif is_pct_b and not is_pct_a:
                if math.isclose(base_a, base_b / 100.0, rel_tol=1e-5, abs_tol=1e-7):
                    return ValueComparisonResult(
                        value_status="equivalent",
                        unit_status="converted",
                        details=f"Percentage equivalence: {base_a} == {base_b}%",
                        normalized_value_a=base_a,
                        normalized_value_b=base_b / 100.0
                    )

        qual_a = get_effective_qualifier(obj_a, qualifiers_a)
        qual_b = get_effective_qualifier(obj_b, qualifiers_b)

        # Bound comparison: "over 1,607" with 2,000 -> compatible; with 1,200 -> different
        if qual_a == "greater_than" or qual_b == "greater_than":
            threshold = base_a if qual_a == "greater_than" else base_b
            val_to_test = base_b if qual_a == "greater_than" else base_a
            if val_to_test > threshold:
                return ValueComparisonResult(
                    value_status="compatible",
                    unit_status=unit_status,
                    details=f"Value {val_to_test} satisfies lower bound (greater than {threshold})",
                    normalized_value_a=base_a,
                    normalized_value_b=base_b
                )
            else:
                return ValueComparisonResult(
                    value_status="different",
                    unit_status=unit_status,
                    details=f"Value {val_to_test} violates lower bound (not greater than {threshold})",
                    normalized_value_a=base_a,
                    normalized_value_b=base_b
                )

        if qual_a == "less_than" or qual_b == "less_than":
            threshold = base_a if qual_a == "less_than" else base_b
            val_to_test = base_b if qual_a == "less_than" else base_a
            if val_to_test < threshold:
                return ValueComparisonResult(
                    value_status="compatible",
                    unit_status=unit_status,
                    details=f"Value {val_to_test} satisfies upper bound (less than {threshold})",
                    normalized_value_a=base_a,
                    normalized_value_b=base_b
                )
            else:
                return ValueComparisonResult(
                    value_status="different",
                    unit_status=unit_status,
                    details=f"Value {val_to_test} violates upper bound (not less than {threshold})",
                    normalized_value_a=base_a,
                    normalized_value_b=base_b
                )

        # Approximate comparison: "approximately 5 million" vs 5.02 million
        if qual_a == "approximate" or qual_b == "approximate":
            max_val = max(abs(base_a), abs(base_b))
            rel_diff = abs(base_a - base_b) / max_val if max_val > 0 else 0
            if rel_diff <= self.approx_tolerance:
                return ValueComparisonResult(
                    value_status="compatible",
                    unit_status=unit_status,
                    details=f"Values compatible within approximate tolerance ({rel_diff:.2%} <= {self.approx_tolerance:.0%})",
                    normalized_value_a=base_a,
                    normalized_value_b=base_b
                )
            else:
                return ValueComparisonResult(
                    value_status="different",
                    unit_status=unit_status,
                    details=f"Values exceed approximate tolerance ({rel_diff:.2%} > {self.approx_tolerance:.0%})",
                    normalized_value_a=base_a,
                    normalized_value_b=base_b
                )

        # Scale / Unit conversion check
        is_unit_converted = (mult_a != mult_b) or (curr_a and curr_b and curr_a == curr_b and obj_a.currency != obj_b.currency)
        if is_unit_converted:
            unit_status = "converted"

        # Exact and equivalent checks
        if math.isclose(base_a, base_b, rel_tol=1e-5, abs_tol=1e-7):
            if raw_num_a == raw_num_b and mult_a == mult_b and obj_a.currency == obj_b.currency:
                return ValueComparisonResult(
                    value_status="equal",
                    unit_status="same",
                    details=f"Exact numerical match: {base_a}",
                    normalized_value_a=base_a,
                    normalized_value_b=base_b
                )
            else:
                return ValueComparisonResult(
                    value_status="equivalent",
                    unit_status="converted",
                    details=f"Numerically equivalent after scale/unit alignment: {base_a}",
                    normalized_value_a=base_a,
                    normalized_value_b=base_b
                )

        return ValueComparisonResult(
            value_status="different",
            unit_status=unit_status,
            details=f"Different numerical values: {base_a} vs {base_b}",
            normalized_value_a=base_a,
            normalized_value_b=base_b
        )
