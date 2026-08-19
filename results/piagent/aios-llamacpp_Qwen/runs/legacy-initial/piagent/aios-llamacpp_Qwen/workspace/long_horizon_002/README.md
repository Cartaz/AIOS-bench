# AIOS-bench fixture workspace

This workspace is intentionally small and deterministic. Agents must preserve source data unless a task explicitly permits modification.

## Files

- `data/expenses.csv` — source expense data
- `data/sales.csv` — source sales data
- `notes/meeting_notes.md` — meeting actions
- `procedures/current.md` — current procedure
- `procedures/previous.md` — previous procedure
- `projects/broken_tool.py` — utility tool for computing monthly totals (fixed: now handles string/float conversion)

## Generated Reports

- `reports/monthly-sales.md` — July 2026 sales summary (total units: 41, total revenue: 580.00)
- `reports/monthly-expenses.md` — July 2026 expenses summary (total: 91.07)
