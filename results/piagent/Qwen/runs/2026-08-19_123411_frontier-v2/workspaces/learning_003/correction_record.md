# Correction Record — Learning Workflow

## Date
2026-08-19

## Issue Detected
The reusable procedure `projects/broken_tool.py` contained a function `monthly_total()` that
performed direct `+=` accumulation on input values.  When values arrived as **strings**
(e.g. `"30"` from CSV data), the function raised a `TypeError`:

```
TypeError: unsupported operand type(s) for +=: 'int' and 'str'
```

This is a **silent-data-type bug**: the function looked correct (summing numbers) but would
fail in any real pipeline that consumed CSV data without an explicit conversion step.  A
developer might wrap it in try/except or coerce inputs inconsistently, producing plausible
but wrong results.

## Root Cause
Line 4 of `broken_tool.py`:
```python
total += value          # crashes if value is a string like "30"
```

The function did not guard against non-numeric types, despite the docstring-like expectation
that it handles numeric data from CSV exports.

## Correction Applied
Modified `projects/broken_tool.py` to convert each value to `float` before adding:

```python
def monthly_total(values):
    """Sum a list of numeric values, converting strings to numbers.

    This is a reusable procedure for computing monthly totals from
    data sources (e.g. CSV rows) where numeric fields may arrive as
    strings.  The original version silently failed on string inputs,
    which could produce incorrect results when used in a pipeline.
    """
    total = 0
    for value in values:
        total += float(value)   # ← fix: explicit numeric conversion
    return total
```

## Evidence

### Before (broken)
```
$ python3 projects/broken_tool.py
TypeError: unsupported operand type(s) for +=: 'int' and 'str'
```

### After (fixed)
```
$ python3 projects/broken_tool.py
monthly_total([10, 20, '30']) = 60.0
```

### Independent validation (validate.py)
- Computed totals from raw `data/sales.csv`: **41 units**, **$580.00 revenue**
- `monthly_total()` on the same data: **41.0 units**, **$580.00 revenue** — ✅ MATCH
- Report generated at `reports/monthly-sales.md` with correct figures

## Files Changed
| File | Change |
|---|---|
| `projects/broken_tool.py` | Fixed `monthly_total()` to convert values to `float` |
| `projects/validate.py` | New: independent validation script |
| `reports/monthly-sales.md` | New: corrected monthly sales summary |

## Re-run of Workflow
After applying the fix, the full workflow was re-run:
1. ✅ Read and validated CSV header and numeric fields
2. ✅ Calculated total revenue ($580.00) and units (41)
3. ✅ Saved summary to `reports/monthly-sales.md`
4. ✅ Independent validation passed
5. ✅ Review step completed
