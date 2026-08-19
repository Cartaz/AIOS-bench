# Reusable Monthly Sales Report Procedure

## Prerequisites
- Source file: `data/sales.csv` with columns: `date,product,units,revenue`
- Output directory: `reports/` (create if missing)

## Steps

1. **Export the monthly sales CSV**
   - Confirm `data/sales.csv` exists and is readable.

2. **Validate the header and numeric fields**
   - Check that the header row is `date,product,units,revenue`.
   - Verify that all values in the `units` and `revenue` columns are numeric integers.
   - Count total data rows (excluding header).

3. **Calculate total revenue and units**
   - Sum all values in the `revenue` column → total revenue.
   - Sum all values in the `units` column → total units sold.
   - Optionally: compute per-product breakdown (sum units and revenue per product).

4. **Save the summary as `reports/monthly-sales.md`**
   - Create a Markdown report with:
     - Title with month and year
     - Overview table: total revenue and total units
     - Per-product breakdown table
     - Full transaction table from source CSV
   - Ensure output directory `reports/` exists (`mkdir -p reports`).

5. **Review the result before sharing**
   - Cross-check totals in the report against source CSV.
   - Confirm formatting and completeness.
   - Do NOT skip this step (previous procedure had this gap).

## Notes
- **Source data must not be modified** unless a task explicitly allows it.
- Use `.md` (Markdown) format for the report, not `.txt` (improvement over previous procedure).
