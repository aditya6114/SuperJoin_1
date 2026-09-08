import re
from typing import Optional
from ..models import TemporalContext
from ..rules.patterns import (
    FISCAL_YEAR_PATTERN,
    CALENDAR_YEAR_PATTERN,
    QUARTER_PATTERN,
    SPECIFIC_DATE_PATTERN,
)

def extract_temporal_context(text: str) -> TemporalContext:
    """
    Extracts explicit temporal expressions from text.
    Never infers missing dates: returns time_type='unknown' if no explicit time is established.
    """
    if not text:
        return TemporalContext(time_type="unknown", value=None)

    # 1. As of Date / For the year ended / Specific Date
    # Check for "as of <date>"
    as_of_match = re.search(
        r'\bas\s+of\s+([A-Za-z]+(?:\.|\s+)\d{1,2},?\s+\d{2,4})\b',
        text,
        re.IGNORECASE
    )
    if as_of_match:
        return TemporalContext(
            time_type="as_of_date",
            value=f"as of {as_of_match.group(1)}"
        )

    # Check for "for the year ended <date>"
    year_ended_match = re.search(
        r'\bfor\s+the\s+year\s+ended\s+([A-Za-z]+(?:\.|\s+)\d{1,2},?\s+\d{2,4})\b',
        text,
        re.IGNORECASE
    )
    if year_ended_match:
        return TemporalContext(
            time_type="date_range",
            value=f"for the year ended {year_ended_match.group(1)}"
        )

    # Specific date (e.g. "March 31, 2024", "December 31, 2021")
    date_match = SPECIFIC_DATE_PATTERN.search(text)
    if date_match:
        return TemporalContext(
            time_type="specific_date",
            value=date_match.group(1).strip()
        )

    # 2. Quarter (e.g. Q3 FY2025, Q1 2024)
    q_match = QUARTER_PATTERN.search(text)
    if q_match:
        return TemporalContext(
            time_type="quarter",
            value=q_match.group(0).strip()
        )

    # 3. Fiscal Year (e.g. FY2022, FY 2021-22, FY21)
    fy_match = FISCAL_YEAR_PATTERN.search(text)
    if fy_match:
        return TemporalContext(
            time_type="fiscal_year",
            value=fy_match.group(1).strip()
        )

    # 4. "During <year>" or standalone Calendar Year (e.g. 2022, 2023)
    during_match = re.search(r'\bduring\s+(\d{4})\b', text, re.IGNORECASE)
    if during_match:
        return TemporalContext(
            time_type="calendar_year",
            value=f"during {during_match.group(1)}"
        )

    # Standalone calendar year (e.g. "in 2021", or a clean 4-digit year)
    cal_match = re.search(r'\b(in\s+)?(19\d{2}|20\d{2})\b', text, re.IGNORECASE)
    if cal_match:
        year = cal_match.group(2)
        return TemporalContext(
            time_type="calendar_year",
            value=year
        )

    # Explicitly do NOT infer missing dates
    return TemporalContext(time_type="unknown", value=None)
