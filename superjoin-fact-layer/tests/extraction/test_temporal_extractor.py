from superjoin.extraction.extractors.temporal_extractor import extract_temporal_context

def test_extract_fiscal_years():
    t1 = extract_temporal_context("Revenue reported for FY2022 was ₹1,000 million.")
    assert t1.time_type == "fiscal_year"
    assert t1.value == "FY2022"

    t2 = extract_temporal_context("Results for FY 2021-22 showed strong improvement.")
    assert t2.time_type == "fiscal_year"
    assert "FY 2021-22" in t2.value

def test_extract_calendar_years():
    t = extract_temporal_context("During 2023, the business expanded into 5 new regions.")
    assert t.time_type == "calendar_year"
    assert "2023" in t.value

def test_extract_quarters():
    t = extract_temporal_context("Operating income for Q3 FY2025 exceeded expectations.")
    assert t.time_type == "quarter"
    assert t.value == "Q3 FY2025"

def test_extract_specific_dates_and_as_of():
    t1 = extract_temporal_context("As of December 31, 2021, cash reserves were strong.")
    assert t1.time_type == "as_of_date"
    assert "December 31, 2021" in t1.value

    t2 = extract_temporal_context("For the year ended March 31, 2024, volume increased.")
    assert t2.time_type == "date_range"
    assert "March 31, 2024" in t2.value

    t3 = extract_temporal_context("The contract was signed on March 31, 2024.")
    assert t3.time_type == "specific_date"
    assert "March 31, 2024" in t3.value

def test_missing_time_returns_unknown_without_inference():
    # Prompt invariant: Do not infer missing dates!
    t = extract_temporal_context("Revenue was ₹500 million.")
    assert t.time_type == "unknown"
    assert t.value is None
