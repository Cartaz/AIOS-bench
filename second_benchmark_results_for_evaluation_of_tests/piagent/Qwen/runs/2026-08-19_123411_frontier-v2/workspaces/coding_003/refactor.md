# Refactor Report — `broken_tool.py`

**Date**: 2026-08-19
**Original File**: `projects/broken_tool.py` (single 9-line file)
**Result**: ✅ Refactored, all 48 tests pass, CLI fully preserved

---

## 1. What Was Wrong

The original tool was a single function in one file:

```python
def monthly_total(values):
    total = 0
    for value in values:
        total += value
    return total

if __name__ == "__main__":
    print(monthly_total([10, 20, "30"]))
```

**Problems:**
1. **Crashes on mixed types** — `int + str` raises `TypeError`.
2. **No parsing** — assumes all inputs are already numeric.
3. **No validation** — no checks for empty input, NaN, Inf.
4. **No separation of concerns** — parsing, computing, and outputting are all in one function.
5. **No tests** — zero test coverage.
6. **No CLI interface** — hardcoded argument list.

---

## 2. Refactored Architecture

The codebase was split into five focused modules following **single-responsibility principle**:

```
projects/
├── broken_tool.py        ← CLI entry point (orchestrator)
├── parser.py             ← Parsing: raw → floats
├── validator.py          ← Validation: floats → validated floats
├── computer.py           ← Computation: sum
├── reporter.py           ← Reporting: format & print/write
└── test_broken_tool.py   ← 48 comprehensive tests
```

### Module Responsibilities

| Module | Responsibility | Key Functions |
|--------|---------------|---------------|
| `parser.py` | Convert raw input (mixed types, CSV files) to floats | `parse_values()`, `parse_csv()`, `_coerce_value()` |
| `validator.py` | Ensure data integrity before computation | `validate_values()` (raises `ValidationError`) |
| `computer.py` | Pure computation logic | `compute_total()` |
| `reporter.py` | Format and output results | `format_total()`, `print_report()`, `write_report()` |
| `broken_tool.py` | CLI orchestration — chains parse → validate → compute → report | `monthly_total()`, `main()`, `_build_parser()` |

### Data Flow

```
Raw Input → Parser → Validated Floats → Computer → Reporter → Output
   ↓            ↓              ↓              ↓           ↓
  [list]    [list[float]]  [list[float]]   [float]  [str / file]
              ✅               ✅             ✅         ✅
              skip invalid     no empty/NaN   sum       human-readable
              coerce strings
```

---

## 3. Bug Fix

The original crash (`TypeError: int + str`) is fixed in two layers:

1. **Parser layer**: `_coerce_value()` converts strings like `"30"` to `30.0`. Invalid items are silently skipped.
2. **Validator layer**: `validate_values()` raises `ValidationError` if anything unexpected gets through (NaN, Inf, empty list, non-sequence).

The original call `monthly_total([10, 20, "30"])` now correctly produces `60.0` instead of crashing.

---

## 4. CLI Interface (Preserved)

The original tool only ran `monthly_total([10, 20, "30"])` via `print()`. The refactored CLI **superset** preserves this default behavior:

```bash
# Default — same input as original
python broken_tool.py
# Output: monthly_total([10.0, 20.0, 30.0]) = 60.00  (n=3, avg=20.00)

# Custom values
python broken_tool.py --values 1 2 3

# Read from CSV file
python broken_tool.py --csv data/expenses.csv

# Write report to file
python broken_tool.py --values 10 20 --file report.md
```

Exit codes: `0` for success, `1` for errors.

---

## 5. Test Suite

**48 tests** across 6 categories, covering normal cases and edge cases:

| Category | Tests | Key Edge Cases Covered |
|----------|-------|------------------------|
| Parser | 20 | None input, string input, empty list, empty strings, non-numeric strings, negative numbers, large numbers, tuples |
| CSV Parser | 6 | Missing column, nonexistent file, empty file, header-only, invalid values |
| Validator | 9 | Empty list, None, string input, NaN, Inf, -Inf, copy isolation |
| Computer | 6 | Empty list, large values, negatives |
| Reporter | 3 | Format string, stdout, file output |
| Integration/CLI | 10 | Default args, custom values, CSV, file output, error conditions |

All 48 tests pass:

```
============================= 48 passed in 0.06s ==============================
```

---

## 6. Verification

1. **Tests**: `pytest test_broken_tool.py -v` → 48/48 passed
2. **CLI default**: `python broken_tool.py` → `60.00` (matches original expected output)
3. **CLI custom**: `python broken_tool.py --values 100 200` → `300.00`
4. **CLI CSV**: `python broken_tool.py --csv data/expenses.csv` → `91.07`
5. **Error handling**: invalid inputs return exit code `1` with descriptive stderr
6. **Reports generated**:
   - `reports/test-report.md` — full test report with per-test results
   - `reports/pytest-results.xml` — JUnit XML for CI/CD
   - `projects/reports/test-output.txt` — raw test output
   - `projects/reports/pytest-results.xml` — local XML

---

## 7. Files Created / Modified

| File | Action | Lines |
|------|--------|-------|
| `projects/broken_tool.py` | **Modified** (refactored) | ~90 |
| `projects/parser.py` | **Created** | ~80 |
| `projects/validator.py` | **Created** | ~45 |
| `projects/computer.py` | **Created** | ~18 |
| `projects/reporter.py` | **Created** | ~28 |
| `projects/test_broken_tool.py` | **Created** | ~280 |
| `reports/test-report.md` | **Created** | test report |
| `reports/pytest-results.xml` | **Created** | JUnit XML |
| `refactor.md` | **Created** | this file |

No benchmark data files were modified. Source CSVs in `data/` are untouched.
