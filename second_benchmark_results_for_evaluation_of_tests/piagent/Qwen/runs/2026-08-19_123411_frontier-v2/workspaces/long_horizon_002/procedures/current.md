# Current procedure

1. Export the monthly sales CSV (`data/sales.csv`).
2. Validate the header and numeric fields (see `projects/monthly_sales.py`).
3. Calculate total revenue and units.
4. Save the summary as `reports/monthly-sales.md` (run: `python projects/monthly_sales.py`).
5. Review the result before sharing it.

## Notes

- The `broken_tool.py` utility has been fixed: `monthly_total()` now coerces all inputs to `float`.
- Invalid data rows are logged as warnings rather than causing failures.
- Reports include a per-product breakdown table.
