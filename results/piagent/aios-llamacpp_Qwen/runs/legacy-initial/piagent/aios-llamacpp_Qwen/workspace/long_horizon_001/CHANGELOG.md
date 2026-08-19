# Changelog

## Changes Made

### 1. Fixed `projects/broken_tool.py`
- **Bug**: `monthly_total([10, 20, "30"])` passed a string `"30"` in a list of integers, causing a `TypeError`.
- **Fix**: Changed `"30"` to `30` (integer).
- **Verification**: Script now runs successfully, outputting `60`.

### 2. Created `projects/analyze_sales.py`
- New analysis script following the current procedure (procedures/current.md):
  1. Loads `data/sales.csv`
  2. Validates header columns and numeric fields
  3. Calculates total revenue ($580.00), total units (41), per-product breakdown
  4. Generates a Markdown report saved to `reports/monthly-sales.md`
  5. Prints report for review

### 3. Generated `reports/monthly-sales.md`
- Monthly Sales Report for July 2026 with summary table, per-product breakdown, and transaction list.
- All figures verified against source CSV.

### 4. Created `reports/` directory
- Output directory for the monthly sales report as required by the procedure.
