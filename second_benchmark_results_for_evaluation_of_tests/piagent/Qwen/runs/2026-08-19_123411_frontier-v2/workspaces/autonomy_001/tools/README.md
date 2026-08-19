# tools/

Utility scripts for the workspace.

## expense_report.py

A reusable Python script that reads `data/expenses.csv` and generates a
`reports/monthly_expense_report.md` with:

- Monthly and category breakdowns
- Detailed transaction listing
- Cross-validated totals

### Prerequisites

- Python 3.9+ (uses only standard library modules)

### Usage

```bash
# Run from workspace root
python3 tools/expense_report.py

# Or specify a workspace path
python3 tools/expense_report.py --workspace /path/to/workspace
```

### What it does

1. **Loads** `data/expenses.csv`, validating columns, dates, and amounts.
2. **Aggregates** totals by month and category.
3. **Validates** that row sums, category subtotals, and monthly subtotals all reconcile.
4. **Renders** a Markdown report and saves it to `reports/monthly_expense_report.md`.

### Output

The report includes summary metrics, monthly and category tables,
a detail transaction list, and a validation section confirming
internal consistency.
