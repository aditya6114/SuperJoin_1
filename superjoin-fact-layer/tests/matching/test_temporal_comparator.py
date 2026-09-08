import pytest
from superjoin.extraction.models import TemporalContext
from superjoin.matching.temporal_comparator import TemporalComparator


def test_same_fiscal_year():
    comp = TemporalComparator()
    t1 = TemporalContext(time_type="fiscal_year", value="FY2024")
    t2 = TemporalContext(time_type="fiscal_year", value="FY 2024")

    res = comp.compare(t1, t2)
    assert res.status == "same"


def test_different_fiscal_years():
    comp = TemporalComparator()
    t1 = TemporalContext(time_type="fiscal_year", value="FY2023")
    t2 = TemporalContext(time_type="fiscal_year", value="FY2024")

    res = comp.compare(t1, t2)
    assert res.status == "different"


def test_quarter_contained_in_fiscal_year():
    comp = TemporalComparator()
    t1 = TemporalContext(time_type="quarter", value="Q1 FY2024")
    t2 = TemporalContext(time_type="fiscal_year", value="FY2024")

    res = comp.compare(t1, t2)
    assert res.status == "contained"


def test_calendar_years():
    comp = TemporalComparator()
    t1 = TemporalContext(time_type="calendar_year", value="2024")
    t2 = TemporalContext(time_type="calendar_year", value="2024")
    t3 = TemporalContext(time_type="calendar_year", value="2023")

    assert comp.compare(t1, t2).status == "same"
    assert comp.compare(t1, t3).status == "different"


def test_fiscal_year_vs_calendar_year_overlap():
    comp = TemporalComparator()
    t1 = TemporalContext(time_type="fiscal_year", value="FY2024")
    t2 = TemporalContext(time_type="calendar_year", value="2024")

    res = comp.compare(t1, t2)
    assert res.status == "overlapping"


def test_specific_dates():
    comp = TemporalComparator()
    t1 = TemporalContext(time_type="specific_date", value="December 31, 2021")
    t2 = TemporalContext(time_type="specific_date", value="December 31, 2021")
    t3 = TemporalContext(time_type="specific_date", value="December 31, 2020")

    assert comp.compare(t1, t2).status == "same"
    assert comp.compare(t1, t3).status == "different"


def test_unknown_time():
    comp = TemporalComparator()
    t1 = TemporalContext(time_type="unknown", value=None)
    t2 = TemporalContext(time_type="fiscal_year", value="FY2024")
    t3 = TemporalContext(time_type="unknown", value=None)

    assert comp.compare(t1, t2).status == "unknown"
    assert comp.compare(t1, t3).status == "unknown"
