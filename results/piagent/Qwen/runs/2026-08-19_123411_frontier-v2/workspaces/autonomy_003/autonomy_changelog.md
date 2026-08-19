# Autonomy Changelog

## 2026-08-19 — Fix `monthly_total` string coercion bug

### Problem
`monthly_total()` crashed with `TypeError: unsupported operand type(s) for +=: 'int' and 'str'` when given a list containing string representations of numbers (e.g. `[10, 20, "30"]`). This broke its use case of summing values that may originate from CSV parsing where all fields arrive as strings.

### Root Cause
The function iterated over `values` and added each item directly to `total` without converting non-numeric types. Python's `+=` operator does not implicitly coerce strings to numbers, so `int + str` raises `TypeError`.

### Fix
Changed `total += value` to `total += float(value)`, which safely converts every element (int, float, or numeric string) to a float before accumulation. The return value is then smartly cast back to `int` when the total is a whole number, preserving type ergonomics for callers.

### Tests Added (`projects/test_broken_tool.py`)
14 regression tests covering:
- Simple integers, empty list, single value
- String numbers, mixed int/str, all-string lists
- Floats, mixed int/float, string+float
- Negative values, zero (int and string), large values
- Type check: result is always a number

All 14 new tests + all 9 pre-existing benchmark tests pass.

### Files Modified
- `projects/broken_tool.py` — fixed `monthly_total()` (2 lines changed)
- `projects/test_broken_tool.py` — added (new, 14 tests)
