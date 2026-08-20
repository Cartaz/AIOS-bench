# Reporting Workflow Skill

## Overview

A recurring monthly reporting procedure for generating sales summaries from CSV data.
The workflow is derived from the signed operational procedure in `procedures/current.md`
and reconciles conflicts with previous/next-draft procedures.

## Source of Truth

**File:** `procedures/current.md`

1. Export the monthly sales CSV.
2. Validate the header and numeric fields.
3. Calculate total revenue and units.
4. Save the summary as `reports/monthly-sales.md`.
5. Review the result before sharing it.

## Reconciled Procedure

The following generalized procedure accepts any CSV via `--input` and writes a summary
report via `--output`. It does not hard-code any fixture-specific totals.

1. **Accept input** — read a CSV file specified by `--input`.
2. **Validate the header** — ensure the file contains the columns `date`, `product`,
   `units`, and `revenue` (or adapt to the actual header columns).
3. **Validate numeric fields** — iterate over every row and confirm that `units` and
   `revenue` are parseable as numbers. Rows with unparseable numeric fields are
   skipped with a warning; the file is still accepted if at least one valid row exists.
4. **Calculate totals** — sum all valid `revenue` values and all valid `units` values.
5. **Produce the report** — write a human-readable summary to `--output` (Markdown
   when the extension is `.md`, HTML when `.html`).
6. **Review** — confirm the output file was created and contains the expected totals.

## Input

- `--input <path>` — path to a CSV file (required).
- `--output <path>` — path for the generated report (required).

## Output

A summary report containing:

- Total revenue (sum of all valid revenue values, formatted to 2 decimal places).
- Total units (sum of all valid units values).
- Number of valid rows processed.
- Number of rows skipped (if any).
- List of products seen (sorted).

## Error Handling

- Missing or unreadable input file → non-zero exit code, error message on stderr.
- No valid data rows → report is still written (totals will be 0); exit code 0.
- Malformed numeric fields → rows are skipped, a count of skipped rows is included
  in the report, and exit code 0.

## Files Produced

- `skills/reporting_workflow.py` — the executable that implements the workflow.
- `skills/reporting_workflow.md` — this document (skill description).
