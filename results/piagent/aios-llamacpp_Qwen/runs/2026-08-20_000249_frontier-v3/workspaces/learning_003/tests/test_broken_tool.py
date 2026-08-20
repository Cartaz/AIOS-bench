from projects.broken_tool import monthly_total

def test_mixed_numeric_input():
    assert monthly_total([10,20,'30']) == 60.0
