# Working Notes — Long Horizon Task 003

## Business Problem Statement
A small team needs to:
1. Generate a July 2026 monthly sales summary from sales.csv
2. Follow the current operating procedure (not the broken previous one)
3. Fix the broken_tool.py (monthly_total has a type error — "30" is a string, not int)
4. Reconcile contradictions between procedures (current vs previous)
5. Produce a final deliverable: reports/monthly-sales.md

## Sources Examined

### data/sales.csv
- 6 records, all July 2026
- Products: A, B, C
- Columns: date, product, units, revenue

### data/expenses.csv
- 6 records, all July 2026
- Categories: software (3), office (2), travel (1)
- Columns: date, category, description, amount

### notes/meeting_notes.md (2026-07-31)
- Decisions: review software subscriptions monthly, keep cloud storage for now
- Actions: Marta to prepare July sales summary, Luca to update procedure

### procedures/current.md
- 5-step procedure
- Outputs to reports/monthly-sales.md
- Includes review step before sharing

### procedures/previous.md
- 4-step procedure
- Outputs to reports/monthly-sales.txt (old format)
- NO review step (procedural gap)

### projects/broken_tool.py
- monthly_total function iterates and sums values
- Bug: passing "30" (string) instead of 30 (int) causes TypeError
- Called in __main__ block with mixed types

## Requirements Audit

### Req 1: Generate monthly sales summary
- Source: data/sales.csv
- Output: reports/monthly-sales.md
- Must include total revenue and total units

### Req 2: Follow current procedure
- Current procedure is the authoritative one (not previous)
- Must output .md (not .txt)
- Must include review step

### Req 3: Fix broken_tool.py
- String "30" causes TypeError on addition with int total
- Fix: convert to numeric or use proper types

### Req 4: Reconcile contradictions
- Previous procedure: no review step, outputs .txt
- Current procedure: has review step, outputs .md
- Resolution: current procedure supersedes previous (date confirms: current is the updated version)

### Req 5: Analyze expenses (meeting notes mention reviewing software subscriptions)
- Software costs: Editor $19.99 x 2 = $39.98, Cloud storage $9.99
- Total software: $49.97/month
- Per meeting notes, review recurring software costs monthly

### Req 6: Produce final deliverable
- reports/monthly-sales.md with full summary
- Include expense analysis context

## Contradictions Identified & Resolved

1. **Output format**: previous=.txt vs current=.md → Use .md (current is authoritative)
2. **Review step**: previous=skip review vs current=require review → Use review step (current is authoritative)
3. **broken_tool.py**: Bug is clear — string in numeric context. Fix by ensuring numeric types.

## Calculations

### Sales (from sales.csv):
- Product A: 10+12+8 = 30 units, $100+$120+$80 = $300
- Product B: 4+5 = 9 units, $80+$100 = $180
- Product C: 2 units, $100
- TOTAL: 41 units, $580 revenue

### Expenses (from expenses.csv):
- Software: $19.99+$9.99+$19.99+$28.40+$8.20... wait, let me recheck
- Software: Editor $19.99, Cloud storage $9.99, Editor $19.99 = $49.97
- Office: Notebook $4.50, Printer paper $8.20 = $12.70
- Travel: Train $28.40
- TOTAL: $91.07
