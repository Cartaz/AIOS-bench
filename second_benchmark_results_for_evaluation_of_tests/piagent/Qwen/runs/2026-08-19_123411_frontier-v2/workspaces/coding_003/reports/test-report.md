# Test Report — Refactored Monthly-Total Tool

**Date**: 2026-08-19
**Test Framework**: pytest 9.1.1
**Result**: ✅ ALL 48 PASSED — 0 FAILED

---

## Summary

| Module            | Tests | Passed | Failed |
|-------------------|-------|--------|--------|
| Parser            | 20    | 20     | 0      |
| Validator         | 9     | 9      | 0      |
| Computer          | 6     | 6      | 0      |
| Reporter          | 3     | 3      | 0      |
| MonthlyTotal wrapper | 4  | 4      | 0      |
| CLI integration   | 6     | 6      | 0      |
| **Total**         | **48**| **48** | **0**  |

---

## Test Categories

### Parser (`parser.py`) — 20 tests

| Test | Description | Result |
|------|-------------|--------|
| test_mixed_types | `[10, 20, "30"]` → `[10.0, 20.0, 30.0]` | ✅ |
| test_all_floats | Float-only input | ✅ |
| test_all_strings | String-only input | ✅ |
| test_negative_numbers | Negative int/float/string | ✅ |
| test_empty_string_skipped | `""` and `"  "` skipped | ✅ |
| test_non_numeric_strings_skipped | `"abc"` silently skipped | ✅ |
| test_all_invalid_returns_empty | `["abc"]` → `[]` | ✅ |
| test_none_input_returns_none | `None` → `None` | ✅ |
| test_string_input_returns_none | `"not a list"` → `None` | ✅ |
| test_empty_list | `[]` → `[]` | ✅ |
| test_zero_values | `0`, `"0"`, `0.0` | ✅ |
| test_large_numbers | `1e10` values | ✅ |
| test_negative_strings | `"-5"`, `"-3.5"` | ✅ |
| test_tuple_input | Tuple accepted | ✅ |
| test_valid_csv | 2-row CSV parsed | ✅ |
| test_csv_non_numeric | Invalid rows skipped | ✅ |
| test_missing_amount_column | No "amount" → `None` | ✅ |
| test_nonexistent_file | Missing file → `None` | ✅ |
| test_empty_file | Empty file → `None` | ✅ |
| test_csv_only_header | Header only → `None` | ✅ |

### Validator (`validator.py`) — 9 tests

| Test | Description | Result |
|------|-------------|--------|
| test_valid_list | Normal list passes | ✅ |
| test_empty_raises | `[]` raises ValidationError | ✅ |
| test_none_raises | `None` raises ValidationError | ✅ |
| test_string_raises | String input raises | ✅ |
| test_nan_raises | NaN raises ValidationError | ✅ |
| test_inf_raises | Inf raises ValidationError | ✅ |
| test_negative_inf_raises | -Inf raises ValidationError | ✅ |
| test_single_value | `[42.0]` passes | ✅ |
| test_returns_copy | Returned list is independent | ✅ |

### Computer (`computer.py`) — 6 tests

| Test | Description | Result |
|------|-------------|--------|
| test_simple_sum | `[10,20,30]` → `60` | ✅ |
| test_floats | `1.1+2.2+3.3` ≈ `6.6` | ✅ |
| test_negative_values | `[-10,10]` → `0` | ✅ |
| test_single_value | `[42]` → `42` | ✅ |
| test_empty_list | `[]` → `0` | ✅ |
| test_large_values | `1e15+1e15` → `2e15` | ✅ |

### Reporter (`reporter.py`) — 3 tests

| Test | Description | Result |
|------|-------------|--------|
| test_format_total | Output contains total, n, avg | ✅ |
| test_print_report | stdout contains formatted output | ✅ |
| test_write_report | File written with expected content | ✅ |

### Wrapper & CLI — 10 tests

| Test | Description | Result |
|------|-------------|--------|
| test_default_mixed | `[10,20,"30"]` → `60.0` | ✅ |
| test_all_valid | `[1,2,3]` → `6.0` | ✅ |
| test_all_invalid_returns_none | `["abc"]` → `None` | ✅ |
| test_none_input_returns_none | `None` → `None` | ✅ |
| test_default_no_args | No args → `60.00` | ✅ |
| test_custom_values | `--values 5 10 15` → `30.00` | ✅ |
| test_csv_file | `--csv` + `--file` write | ✅ |
| test_csv_nonexistent | Bad CSV file → exit 1 | ✅ |
| test_no_valid_values | All invalid → exit 1 | ✅ |
| test_file_output | `--file` writes report | ✅ |

---

## CLI Verification

```
$ python broken_tool.py
monthly_total([10.0, 20.0, 30.0]) = 60.00  (n=3, avg=20.00)

$ python broken_tool.py --values 100 200
monthly_total([100.0, 200.0]) = 300.00  (n=2, avg=150.00)

$ python broken_tool.py --csv ../data/expenses.csv
monthly_total([19.99, 9.99, 4.5, 19.99, 28.4, 8.2]) = 91.07  (n=6, avg=15.18)
```

All CLI modes produce correct output.

---

## Original Bug Fix

The original `broken_tool.py` crashed with:
```
TypeError: unsupported operand type(s) for +=: 'int' and 'str'
```

This was caused by directly summing `[10, 20, "30"]` without type coercion.
The refactored tool's parser silently converts string numbers to floats,
so the same input now produces `monthly_total([10.0, 20.0, 30.0]) = 60.00`
with no errors — matching the expected "preserved behavior" (same output,
no crash).
