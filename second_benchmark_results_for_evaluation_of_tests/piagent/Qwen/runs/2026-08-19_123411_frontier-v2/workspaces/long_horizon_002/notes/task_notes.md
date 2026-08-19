# Task Dependency Chain — Long Horizon 002

## Dependencies
```
broken_tool.py fix  →  monthly_sales.py  →  reports/monthly-sales.md
       │                      │                      │
       ▼                      ▼                      ▼
   validate inputs     run & generate report   save to reports/
       │                      │                      │
       └──────► test invalid inputs ◄───────────────┘
                         │
                         ▼
              update procedures/current.md
                         │
                         ▼
              final verification
```

## Status ✅ ALL COMPLETE
- [x] Step 1: Fix broken_tool.py (TypeError on mixed int/str) → `float(value)` coercion
- [x] Step 2: Build monthly_sales.py reporter (reads CSV, validates, calculates, writes MD)
- [x] Step 3: Run checks and verify output → 41 units, $580.00, per-product breakdown
- [x] Step 4: Test invalid inputs → bad headers, non-numeric fields, short rows, empty lists
- [x] Step 5: Update documentation → procedures/current.md + notes/task_notes.md
- [x] Step 6: Final verification → source data untouched, report correct, all checks pass
