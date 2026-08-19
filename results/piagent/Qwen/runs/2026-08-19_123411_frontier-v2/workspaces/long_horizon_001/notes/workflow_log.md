# Workflow Log — Long Horizon Task

## Step 1: Workspace Inspection (COMPLETE)

### Authoritative Data Sources
1. `data/sales.csv` — Source sales data (6 rows, columns: date, product, units, revenue)
   - Products: A, B, C
   - All July 2026 data
   - Revenue values: 100, 80, 120, 100, 100, 80

2. `data/expenses.csv` — Source expense data (6 rows, columns: date, category, description, amount)
   - Categories: software, office, travel
   - All July 2026 data

3. `notes/meeting_notes.md` — Meeting actions and decisions for July 31, 2026
   - Marta: prepare July sales summary
   - Decisions: keep cloud storage, review software costs monthly

### Procedure Documents
- `procedures/current.md` — Current procedure requires: export CSV, validate header+numeric fields, calculate total revenue & units, save as `reports/monthly-sales.md`, review before sharing
- `procedures/previous.md` — Previous procedure (no review step, .txt output)

### Broken Tool
- `projects/broken_tool.py` — Has a bug: `monthly_total([10, 20, "30"])` will fail because "30" is a string, causing TypeError when adding to int total
- FIX: convert values to float/int before adding

## Step 2: Plan (COMPLETE)
1. Fix the broken_tool.py
2. Run the analysis script to generate monthly-sales.md
3. Validate every requirement
4. Write changelog

## Step 3: Execute Analysis (IN PROGRESS)
