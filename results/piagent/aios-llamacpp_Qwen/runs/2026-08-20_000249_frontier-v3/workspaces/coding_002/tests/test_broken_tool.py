from projects.broken_tool import monthly_total

def test_mixed_numeric_input():
    assert monthly_total([10,20,'30']) == 60.0

def test_all_strings():
    assert monthly_total(['10', '20', '30']) == 60.0

def test_empty_list():
    assert monthly_total([]) == 0.0

def test_all_floats():
    assert monthly_total([1.5, 2.5, 3.0]) == 7.0
