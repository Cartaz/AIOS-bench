# AIOS-bench fixture workspace

This workspace is intentionally small and deterministic. Agents must preserve source data unless a task explicitly permits modification.

## Files

- `data/expenses.csv` — source expense data
- `data/sales.csv` — source sales data
- `notes/meeting_notes.md` — meeting actions
- `procedures/current.md` — current procedure
- `procedures/previous.md` — previous procedure
- `projects/broken_tool.py` — monthly total calculation tool

## Usage

Run the monthly total tool:

```bash
python projects/broken_tool.py
```

The `monthly_total(values)` function accepts a list of numeric values (ints, floats, or numeric strings) and returns their sum.
