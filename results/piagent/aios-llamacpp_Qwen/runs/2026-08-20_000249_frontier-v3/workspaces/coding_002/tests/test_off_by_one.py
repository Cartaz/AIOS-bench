from projects.off_by_one_tool import inclusive_days

def test_inclusive_end_date():
    assert inclusive_days('2026-08-01','2026-08-03') == 3

def test_same_day():
    assert inclusive_days('2026-08-01','2026-08-01') == 1

def test_multi_day():
    assert inclusive_days('2026-01-01','2026-01-31') == 31
