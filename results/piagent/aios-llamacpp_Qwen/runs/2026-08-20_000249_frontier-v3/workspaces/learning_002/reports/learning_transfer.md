# Learning Transfer Report

## Source Procedure (current.md)

1. Export the monthly sales CSV.
2. Validate the header and numeric fields.
3. Calculate total revenue and units.
4. Save the summary as `reports/monthly-sales.md`.
5. Review the result before sharing it.

## Schema Change Detected

| Original Column | New Column   | Change    |
|-----------------|--------------|-----------|
| `date`          | `txn_date`   | Renamed   |
| `product`       | `sku`        | Renamed   |
| `units`         | `qty_sold`   | Renamed   |
| `revenue`       | `gross_usd`  | Renamed   |

All four columns were renamed (schema shift), but the data values remain unchanged.

## Transferred Steps

These steps were applied without modification to the new data:

1. **Export the monthly sales CSV** — read `data/sales_schema_shift.csv` via the workflow tool.
2. **Calculate total revenue and units** — the workflow tool's `compute_totals()` already supports arbitrary column names through keyword matching, so the calculation logic carried over as-is.
3. **Save the summary as `reports/monthly-sales.md`** — same output path and format used.
4. **Review the result before sharing it** — the generated report was inspected and verified (6 valid rows, 0 skipped, totals match expected values).

## Adapted Steps

| Step | Adaptation | Reason |
|------|-----------|--------|
| 2. Validate the header and numeric fields | The header validation was adapted to accept renamed columns. Instead of requiring exact matches for `date`, `product`, `units`, and `revenue`, the `reporting_workflow.py` uses keyword-based column detection: columns containing "txn" or "date" for dates, "sku" or "product" or "item" for products, "qty" or "unit" or "sold" for units, and "gross" or "revenue" or "amount" or "usd" for revenue. | The new CSV (`sales_schema_shift.csv`) uses a different naming convention (`txn_date`, `sku`, `qty_sold`, `gross_usd`). Hard-coded column-name matching would have failed. Keyword-based matching allows the same validation logic to work across schema variants without modification. |

## Execution Result

- **Input file:** `data/sales_schema_shift.csv` (4 columns: `txn_date`, `sku`, `qty_sold`, `gross_usd`)
- **Valid rows processed:** 6
- **Skipped rows:** 0
- **Total Revenue:** 580.00
- **Total Units:** 41
- **Products:** A, B, C
- **Output report:** `reports/monthly-sales.md`
- **Review:** Passed — all rows valid, totals verified.
