# Reporting Workflow — Recurring Monthly Sales Report

## Overview

This document describes the generalised procedure for producing the recurring monthly
sales report.  It is derived from the current operating procedure
(`procedures/current.md`) and the previous iteration
(`procedures/previous.md`).  The workflow is **data-source agnostic**:
it does not encode any fixture-specific totals, product names, or date
ranges.

---

## Prerequisites

| # | Requirement | How to satisfy |
|---|-------------|----------------|
| 1 | **Source CSV exists** at a known path (e.g. `data/sales.csv`) | Confirm the file is present; if missing, halt and alert. |
| 2 | **CSV header** contains at least `units` and `revenue` columns | Inspect the first line; abort if either column is absent. |
| 3 | **Numeric fields** — every value in `units` and `revenue` rows 2…N parses as a number | Run a validation pass (regex `/^[0-9]+$/` or equivalent).  Report the first offending line. |
| 4 | **Output directory** exists (e.g. `reports/`) | Create it with `mkdir -p` if absent. |
| 5 | **Write access** to the output location | Test with a quick `touch`; abort on permission error. |

---

## Step-by-step Procedure

### Step 1 — Export / locate the monthly sales CSV
Identify the source file.  When multiple files exist, select the one
matching the target month (by examining date ranges or filenames).

### Step 2 — Validate header and numeric fields
1. Read the first line and confirm the expected columns are present.
2. For every data row, verify that the `units` and `revenue` columns
   contain valid numbers.
3. Record any validation errors; do **not** proceed if errors exist
   (or apply a defined tolerance such as "skip rows with errors").

### Step 3 — Calculate aggregates
Using the validated rows, compute:
- **total_revenue** = Σ revenue
- **total_units**   = Σ units
- (Optional but recommended) per-product (or per-category) subtotals
  for a breakdown table.

### Step 4 — Save the summary
Write a Markdown report to `reports/monthly-sales.md` (or the
configured output path) containing:
- Report title and period covered
- Total revenue and total units
- A breakdown table (product → units, revenue)
- The source data file reference

### Step 5 — Review before sharing
1. Re-read the generated report.
2. Cross-check the totals against the raw computation output.
3. Confirm the report structure matches the template.
4. Only after this manual (or automated) review is the report shared.

---

## Decision Points

| Decision | Branch A | Branch B |
|----------|----------|----------|
| **Validation fails** | Fix the offending rows in the source CSV, then re-run steps 2–5. | Log the error and notify the report owner; do not generate a partial report. |
| **Source CSV is missing** | Alert the data owner and wait for the file. | If a cached/previous month's CSV exists, flag the report as stale. |
| **Multiple months in source** | Filter rows to the single target month before aggregation. | Produce one report per month in a loop. |
| **Division by zero in averages** | Skip the average metric for that product/month. | Report `N/A` for that cell. |

---

## Validation Checklist

- [ ] CSV header has all expected columns.
- [ ] All numeric fields pass the type check.
- [ ] Total revenue = Σ of individual revenue values.
- [ ] Total units = Σ of individual unit counts.
- [ ] Per-product subtotals sum to the grand totals.
- [ ] Report file is written and readable.
- [ ] Review step completed and signed off.

---

## Recovery Procedures

| Failure Mode | Recovery Action |
|--------------|----------------|
| Source file missing or empty | Re-fetch from the upstream data pipeline; if unavailable, report the issue and defer. |
| Numeric validation failure | Isolate offending rows, attempt automated cleaning (strip commas, handle negatives), or escalate to the data owner. |
| Calculation error (mismatched totals) | Re-run the aggregation with a different tool (e.g. Python instead of awk); compare results. |
| Output file not written | Check disk space and permissions; retry with explicit `mkdir -p`. |
| Review finds incorrect data | Trace the error to step 2 (bad source), step 3 (calculation), or step 4 (formatting) and re-run from that step. |

---

## Generalisation Notes

- **No fixture-specific totals are hardcoded.**  All numbers are
  computed dynamically from the CSV at runtime.
- The procedure works for **any month** and **any product set**; the
  only assumptions are the CSV column names (`units`, `revenue`).
- The report format (Markdown) is configurable — swap to HTML, PDF,
  or JSON by changing only Step 4's output template.
- The review step (Step 5) was **added in the current procedure**
  (`procedures/current.md`) over the previous procedure, which
  skipped review entirely (`procedures/previous.md`).
