import pytest
from superjoin.extraction.models import FactObject
from superjoin.matching.value_comparator import ValueComparator


def test_equivalent_monetary_values_crore_vs_million():
    comp = ValueComparator()
    # ₹5 crore = 50,000,000
    obj_a = FactObject(value_type="currency", value=5, currency="₹", scale="crore")
    # ₹50 million = 50,000,000
    obj_b = FactObject(value_type="currency", value=50, currency="₹", scale="million")

    res = comp.compare(obj_a, obj_b)
    assert res.value_status == "equivalent"
    assert res.unit_status == "converted"
    assert res.normalized_value_a == 50000000.0
    assert res.normalized_value_b == 50000000.0


def test_exact_same_value():
    comp = ValueComparator()
    obj_a = FactObject(value_type="currency", value=500, currency="₹", scale="crore")
    obj_b = FactObject(value_type="currency", value=500, currency="₹", scale="crore")

    res = comp.compare(obj_a, obj_b)
    assert res.value_status == "equal"
    assert res.unit_status == "same"


def test_different_numerical_values():
    comp = ValueComparator()
    obj_a = FactObject(value_type="currency", value=500, currency="₹", scale="crore")
    obj_b = FactObject(value_type="currency", value=600, currency="₹", scale="crore")

    res = comp.compare(obj_a, obj_b)
    assert res.value_status == "different"


def test_percentage_equivalence():
    comp = ValueComparator()
    obj_a = FactObject(value_type="percentage", value=5)
    obj_b = FactObject(value_type="number", value=0.05)

    res = comp.compare(obj_a, obj_b)
    assert res.value_status == "equivalent"


def test_approximate_value_compatible():
    comp = ValueComparator(approx_tolerance=0.05)
    # 5 million with qualifier 'approximate' vs 5.02 million (diff = 0.4%)
    obj_a = FactObject(value_type="number", value=5.0, scale="million", qualifier="approximate")
    obj_b = FactObject(value_type="number", value=5.02, scale="million")

    res = comp.compare(obj_a, obj_b)
    assert res.value_status == "compatible"


def test_approximate_value_exceeds_tolerance():
    comp = ValueComparator(approx_tolerance=0.05)
    obj_a = FactObject(value_type="number", value=5.0, scale="million", qualifier="approximate")
    obj_b = FactObject(value_type="number", value=6.5, scale="million")

    res = comp.compare(obj_a, obj_b)
    assert res.value_status == "different"


def test_lower_bound_qualifier():
    comp = ValueComparator()
    # "over 1,607" with 2,000 -> compatible
    obj_a = FactObject(value_type="number", value=1607, qualifier="greater_than")
    obj_b = FactObject(value_type="number", value=2000)

    res = comp.compare(obj_a, obj_b)
    assert res.value_status == "compatible"

    # "over 1,607" with 1,200 -> different
    obj_c = FactObject(value_type="number", value=1200)
    res_violates = comp.compare(obj_a, obj_c)
    assert res_violates.value_status == "different"


def test_currency_mismatch():
    comp = ValueComparator()
    obj_a = FactObject(value_type="currency", value=500, currency="₹", scale="crore")
    obj_b = FactObject(value_type="currency", value=500, currency="$", scale="crore")

    res = comp.compare(obj_a, obj_b)
    assert res.value_status == "different"
    assert res.unit_status == "different"


def test_text_equality():
    comp = ValueComparator()
    obj_a = FactObject(value_type="text", value="New Delhi")
    obj_b = FactObject(value_type="text", value="new delhi")
    obj_c = FactObject(value_type="text", value="Mumbai")

    assert comp.compare(obj_a, obj_b).value_status == "equal"
    assert comp.compare(obj_a, obj_c).value_status == "different"
