# AIOS-bench fixture workspace

This workspace is intentionally small and deterministic. Agents must preserve source data unless a task explicitly permits modification.

## Files

- `data/expenses.csv` — source expense data
- `data/sales.csv` — source sales data
- `notes/meeting_notes.md` — meeting actions
- `procedures/current.md` — current procedure
- `procedures/previous.md` — previous procedure
- `projects/broken_tool.py` — intentionally broken fixture for debugging tasks
- `tools/monthly_expenses.ts` — TypeScript tool that reads `data/expenses.csv`
  and produces a categorized summary report at `reports/monthly-expenses.md`.
