import pytest
from superjoin.extraction.extractors.numerical_extractor import extract_quantities

def test_extract_currency_and_scale():
    # ₹5 crore
    q1 = extract_quantities("The company generated revenue of ₹5 crore.")
    assert len(q1) == 1
    assert q1[0].value_type == "currency"
    assert q1[0].value == 5
    assert q1[0].currency == "₹"
    assert q1[0].scale == "crore"

    # USD 5.5 billion
    q2 = extract_quantities("Estimated at USD 5.5 billion in total value.")
    assert len(q2) == 1
    assert q2[0].currency == "USD"
    assert q2[0].value == 5.5
    assert q2[0].scale == "billion"

    # ₹50 million
    q3 = extract_quantities("Operating profit reached ₹50 million.")
    assert len(q3) == 1
    assert q3[0].currency == "₹"
    assert q3[0].value == 50
    assert q3[0].scale == "million"

def test_extract_percentages():
    q = extract_quantities("Operating margin expanded by 6.4% while growth was 12.5 percent.")
    assert len(q) == 2
    assert q[0].value_type == "percentage"
    assert q[0].value == 6.4
    assert q[0].unit == "%"
    assert q[1].value_type == "percentage"
    assert q[1].value == 12.5
    assert q[1].unit == "%"

def test_extract_physical_units_and_quantities():
    # 1,607 guards
    q1 = extract_quantities("The facility employs 1,607 guards on site.")
    assert len(q1) == 1
    assert q1[0].value == 1607
    assert q1[0].unit == "guards"

    # 6.25 million sq ft
    q2 = extract_quantities("The total area was 6.25 million sq ft.")
    assert len(q2) == 1
    assert q2[0].value == 6.25
    assert q2[0].scale == "million"
    assert q2[0].unit == "sq ft"

def test_extract_comparative_and_approximate():
    # over 1,607
    q1 = extract_quantities("Total count of guards was over 1,607.")
    assert len(q1) == 1
    assert q1[0].value == 1607
    assert q1[0].qualifier == "greater_than"

    # more than 750
    q2 = extract_quantities("Network covers more than 750 centres.")
    assert len(q2) == 1
    assert q2[0].value == 750
    assert q2[0].qualifier == "greater_than"

    # approximately 5 million
    q3 = extract_quantities("Processed approximately 5 million shipments.")
    assert len(q3) == 1
    assert q3[0].value == 5
    assert q3[0].scale == "million"
    assert q3[0].qualifier == "approximate"
