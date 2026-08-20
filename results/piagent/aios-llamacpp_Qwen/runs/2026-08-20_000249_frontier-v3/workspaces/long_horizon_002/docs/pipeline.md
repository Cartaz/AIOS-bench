# Three-Stage Reporting Pipeline

## Overview

A three-stage data processing pipeline that transforms CSV data into a final report,
with strict dependency chain and error handling at each stage.

## Pipeline Stages

### Stage 1: `tools/step1_summary.py`
- **Input:** CSV file (e.g. `data/sales.csv`)
- **Output:** `reports/summary.json`
- **Function:** Reads CSV, computes per-column statistics (count, sum, mean, min, max),
  produces structured JSON summary. Exits with code 1 if input file is missing.

### Stage 2: `tools/step2_chart.py`
- **Input:** `reports/summary.json` (produced by Stage 1)
- **Output:** `reports/chart.json`
- **Function:** Consumes summary JSON, generates chart-ready data including chart type
  selection, datasets, labels, and metadata. Exits with code 1 if summary is missing.

### Stage 3: `tools/step3_report.py`
- **Input:** `reports/summary.json` + `reports/chart.json`
- **Output:** `reports/final_report.md` (Markdown report)
- **Function:** Combines both upstream artifacts into a human-readable report with
  data summary table, chart details, and insights. Exits with code 1 if either input is missing.

## Running the Pipeline

```bash
# Stage 1
python tools/step1_summary.py --input data/sales.csv --output reports/summary.json

# Stage 2
python tools/step2_chart.py --input reports/summary.json --output reports/chart.json

# Stage 3
python tools/step3_report.py --summary reports/summary.json --chart reports/chart.json --output reports/final_report.md
```

## Additional CLI Tools

### `tools/report_cli.py`
End-to-end CLI that runs the full pipeline on any CSV and produces HTML output.
```bash
python tools/report_cli.py --input data/sales.csv --output report.html
```
Exits with code 1 if input file does not exist.

### `tools/robust_report.py`
Robust plain-text report generator that handles edge cases gracefully (empty datasets,
missing numeric values).
```bash
python tools/robust_report.py --input data/sales.csv --output report.txt
```
Exits with code 1 if input file does not exist; produces valid output for empty datasets.

## Error Handling

All tools validate upstream artifacts exist before processing:
- `step1_summary.py`: checks input CSV exists
- `step2_chart.py`: checks summary JSON exists
- `step3_report.py`: checks both summary and chart JSON exist
- `report_cli.py`: checks input CSV exists
- `robust_report.py`: checks input CSV exists

Missing upstream artifacts cause exit code 1 with an error message to stderr.

## Fixed Bugs

1. **`projects/broken_tool.py`**: `monthly_total()` now converts string values to float
   before summing, so `monthly_total([10, 20, '30'])` returns `60.0` instead of raising TypeError.

2. **`projects/off_by_one_tool.py`**: `inclusive_days()` now returns `(b-a).days + 1` to
   include both start and end dates, so `inclusive_days('2026-08-01', '2026-08-03')` returns `3`.
