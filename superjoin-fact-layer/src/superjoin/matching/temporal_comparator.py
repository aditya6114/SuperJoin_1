import re
from typing import Optional, Tuple
from pydantic import BaseModel
from superjoin.extraction.models import TemporalContext


class TemporalComparisonResult(BaseModel):
    status: str  # "same", "different", "overlapping", "contained", "unknown"
    details: str


def parse_fiscal_year(val: Optional[str]) -> Optional[int]:
    """Extract the ending year of a fiscal year expression (e.g., FY2024 -> 2024, FY24 -> 2024)."""
    if not val:
        return None
    val_clean = val.strip().upper()
    # Match FY2024 or FY 2024
    m = re.search(r"FY\s*(\d{4})", val_clean)
    if m:
        return int(m.group(1))
    # Match FY24
    m = re.search(r"FY\s*(\d{2})\b", val_clean)
    if m:
        return 2000 + int(m.group(1))
    # Match 2023-24 or 2023-2024
    m = re.search(r"(\d{4})\s*-\s*(\d{2,4})", val_clean)
    if m:
        end_part = m.group(2)
        if len(end_part) == 2:
            return 2000 + int(end_part)
        return int(end_part)
    return None


def parse_calendar_year(val: Optional[str]) -> Optional[int]:
    """Extract a 4-digit calendar year."""
    if not val:
        return None
    m = re.search(r"\b(19\d{2}|20\d{2})\b", val.strip())
    if m:
        return int(m.group(1))
    return None


def parse_quarter(val: Optional[str]) -> Optional[Tuple[int, Optional[int]]]:
    """Extract (quarter_num, fiscal_year) e.g., 'Q1 FY2024' -> (1, 2024)."""
    if not val:
        return None
    val_clean = val.strip().upper()
    m_q = re.search(r"\bQ([1-4])\b", val_clean)
    if not m_q:
        m_q = re.search(r"\b(FIRST|SECOND|THIRD|FOURTH)\s+QUARTER\b", val_clean)
        if not m_q:
            return None
        word_map = {"FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4}
        q_num = word_map[m_q.group(1)]
    else:
        q_num = int(m_q.group(1))

    fy = parse_fiscal_year(val_clean)
    return (q_num, fy)


MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12
}


def parse_date_tuple(val: Optional[str]) -> Optional[Tuple[int, int, int]]:
    """Parse string to (year, month, day)."""
    if not val:
        return None
    val_clean = val.strip().lower()

    # ISO format YYYY-MM-DD
    m_iso = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", val_clean)
    if m_iso:
        return (int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))

    # Month Day, Year (e.g. December 31, 2021)
    m_mdy = re.search(r"([a-z]+)\s+(\d{1,2}),?\s+(\d{4})", val_clean)
    if m_mdy and m_mdy.group(1) in MONTH_MAP:
        return (int(m_mdy.group(3)), MONTH_MAP[m_mdy.group(1)], int(m_mdy.group(2)))

    # Day Month Year (e.g. 31 December 2021)
    m_dmy = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", val_clean)
    if m_dmy and m_dmy.group(2) in MONTH_MAP:
        return (int(m_dmy.group(3)), MONTH_MAP[m_dmy.group(2)], int(m_dmy.group(1)))

    return None


class TemporalComparator:
    """Deterministic comparator for TemporalContext across facts."""

    def compare(self, time_a: TemporalContext, time_b: TemporalContext) -> TemporalComparisonResult:
        if not time_a or not time_b:
            return TemporalComparisonResult(status="unknown", details="Missing temporal context.")

        type_a = time_a.time_type
        type_b = time_b.time_type
        val_a = time_a.value.strip() if time_a.value else None
        val_b = time_b.value.strip() if time_b.value else None

        # Unknown time handling
        if type_a == "unknown" or type_b == "unknown" or not val_a or not val_b:
            # If both are explicitly unknown or have no values
            if (type_a == "unknown" or not val_a) and (type_b == "unknown" or not val_b):
                return TemporalComparisonResult(status="unknown", details="Both temporal contexts are unknown.")
            return TemporalComparisonResult(status="unknown", details="One or both temporal contexts are unknown/unspecified.")

        # Exact textual string match
        if val_a.lower() == val_b.lower():
            return TemporalComparisonResult(status="same", details=f"Identical temporal expression: '{val_a}'")

        # Specific dates / As-of dates
        if type_a in {"specific_date", "as_of_date"} and type_b in {"specific_date", "as_of_date"}:
            d_a = parse_date_tuple(time_a.start_date or val_a)
            d_b = parse_date_tuple(time_b.start_date or val_b)
            if d_a and d_b:
                if d_a == d_b:
                    return TemporalComparisonResult(status="same", details=f"Same date: {d_a[0]}-{d_a[1]:02d}-{d_a[2]:02d}")
                return TemporalComparisonResult(status="different", details=f"Different dates: {d_a} vs {d_b}")

        # Fiscal Year vs Fiscal Year
        if type_a == "fiscal_year" and type_b == "fiscal_year":
            fy_a = parse_fiscal_year(val_a)
            fy_b = parse_fiscal_year(val_b)
            if fy_a and fy_b:
                if fy_a == fy_b:
                    return TemporalComparisonResult(status="same", details=f"Same fiscal year: FY{fy_a}")
                return TemporalComparisonResult(status="different", details=f"Different fiscal years: FY{fy_a} vs FY{fy_b}")

        # Calendar Year vs Calendar Year
        if type_a == "calendar_year" and type_b == "calendar_year":
            cy_a = parse_calendar_year(val_a)
            cy_b = parse_calendar_year(val_b)
            if cy_a and cy_b:
                if cy_a == cy_b:
                    return TemporalComparisonResult(status="same", details=f"Same calendar year: {cy_a}")
                return TemporalComparisonResult(status="different", details=f"Different calendar years: {cy_a} vs {cy_b}")

        # Quarter vs Fiscal Year (Containment)
        # e.g., Q1 FY2024 is contained in FY2024
        q_info_a = parse_quarter(val_a) if type_a in {"quarter", "fiscal_year"} else None
        q_info_b = parse_quarter(val_b) if type_b in {"quarter", "fiscal_year"} else None

        if q_info_a and not q_info_b:
            fy_b = parse_fiscal_year(val_b)
            if fy_b and q_info_a[1] == fy_b:
                return TemporalComparisonResult(
                    status="contained",
                    details=f"Quarter '{val_a}' is contained in fiscal year FY{fy_b}"
                )
        elif q_info_b and not q_info_a:
            fy_a = parse_fiscal_year(val_a)
            if fy_a and q_info_b[1] == fy_a:
                return TemporalComparisonResult(
                    status="contained",
                    details=f"Quarter '{val_b}' is contained in fiscal year FY{fy_a}"
                )

        # Fiscal Year vs Calendar Year (Do NOT equate without evidence; mark overlapping)
        fy_val = parse_fiscal_year(val_a) if type_a == "fiscal_year" else (parse_fiscal_year(val_b) if type_b == "fiscal_year" else None)
        cy_val = parse_calendar_year(val_a) if type_a == "calendar_year" else (parse_calendar_year(val_b) if type_b == "calendar_year" else None)

        if fy_val and cy_val:
            # FY2024 typically runs April 2023 to March 2024 (India) or Oct 2023 to Sept 2024 (US)
            # Calendar year 2024 runs Jan 2024 to Dec 2024.
            # They overlap partially, but are distinct.
            if abs(fy_val - cy_val) <= 1:
                return TemporalComparisonResult(
                    status="overlapping",
                    details=f"Fiscal year (FY{fy_val}) and calendar year ({cy_val}) overlap but are distinct accounting periods."
                )
            else:
                return TemporalComparisonResult(
                    status="different",
                    details=f"Distinct non-overlapping fiscal and calendar years: FY{fy_val} vs {cy_val}"
                )

        return TemporalComparisonResult(status="different", details=f"Different temporal contexts: '{val_a}' vs '{val_b}'")
