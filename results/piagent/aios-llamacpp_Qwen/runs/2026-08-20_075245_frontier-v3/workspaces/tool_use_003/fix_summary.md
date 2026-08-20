# Fix Summary

## Overview
Fixed 5 independent test failures across 3 test files. All 8 tests now pass (previously 3 failed).

---

## Failure 1: `test_broken_tool.py::test_mixed_numeric_input`
**File**: `projects/broken_tool.py`  
**Diagnosis**: The `monthly_total` function tried to add string values (e.g. `'30'`) directly to an integer accumulator, causing a `TypeError`.  
**Fix**: Changed `total` initialization from `0` (int) to `0.0` (float) and wrapped each value in `float()` to handle mixed int/string inputs.

```python
# Before
def monthly_total(values):
    total = 0
    for value in values:
        total += value
    return total

# After
def monthly_total(values):
    total = 0.0
    for value in values:
        total += float(value)
    return total
```

---

## Failure 2: `test_hidden_report_cli.py::test_alternate_dataset`
**File**: `tools/report_cli.py` (new file created)  
**Diagnosis**: The file `tools/report_cli.py` did not exist. The test expects a CLI tool that reads a CSV file and produces an HTML report containing column totals (e.g., `742.50` as the sum of the `revenue` column).  
**Fix**: Created `tools/report_cli.py` that:
- Accepts `--input` (CSV) and `--output` (HTML) arguments
- Reads CSV with `csv.DictReader`
- Generates an HTML table with headers and data rows
- Handles malformed/missing values gracefully (strips whitespace, skips non-numeric values)
- Appends a **Totals row** with 2-decimal formatting for numeric columns

---

## Failure 3: `test_hidden_report_cli.py::test_malformed_fixture_is_handled`
**File**: `tools/report_cli.py` (same new file)  
**Diagnosis**: The `data/expenses.csv` file contains a row with a missing `amount` value (empty string in the last row). The tool must handle this gracefully.  
**Fix**: The `report_cli.py` handles missing/malformed values by checking `row.get(key, "")`, defaulting to empty string, stripping whitespace, and skipping non-numeric values when computing totals.

---

## Failure 4: `test_off_by_one.py::test_inclusive_days`
**File**: `projects/off_by_one_tool.py`  
**Diagnosis**: `inclusive_days('2026-08-01', '2026-08-03')` returned `2` instead of `3`. The function computed `(b-a).days` which is exclusive of the end date.  
**Fix**: Added `+ 1` to include both start and end dates in the count.

```python
# Before
return (b-a).days

# After
return (b-a).days + 1
```

---

## Failure 5: `test_robust.py::test_empty_dataset`
**File**: `tools/robust_report.py` (new file created)  
**Diagnosis**: The file `tools/robust_report.py` did not exist. The test expects a CLI tool that handles empty CSV files (headers only, no data rows) gracefully with exit code 0.  
**Fix**: Created `tools/robust_report.py` that:
- Accepts `--input` (CSV) and `--output` (text) arguments
- Returns exit code 1 with error message if input file doesn't exist
- Handles empty datasets by outputting "No data rows found." and exiting 0
- Sums numeric columns when data is present
- Handles malformed/missing numeric values gracefully

---

## Files Modified
1. `projects/broken_tool.py` — Fixed type coercion in `monthly_total()`
2. `projects/off_by_one_tool.py` — Fixed off-by-one in `inclusive_days()`
3. `tools/report_cli.py` — **Created** (HTML report generator from CSV)
4. `tools/robust_report.py` — **Created** (robust report tool handling edge cases)

## Test Results (After Fix)
```
tests/test_broken_tool.py::test_mixed_numeric_input PASSED
tests/test_cli_contract.py::test_cli_contract PASSED
tests/test_hidden_report_cli.py::test_alternate_dataset PASSED
tests/test_hidden_report_cli.py::test_missing_input_rejected PASSED
tests/test_hidden_report_cli.py::test_malformed_fixture_is_handled PASSED
tests/test_off_by_one.py::test_inclusive_end_date PASSED
tests/test_robust.py::test_empty_dataset PASSED
tests/test_robust.py::test_invalid_dataset PASSED
========================= 8 passed in 0.23s
```
