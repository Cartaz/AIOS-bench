# Changelog

## 2026-08-19 — Long Horizon Task Completion

### Files Modified

| File | Action | Reason |
|------|--------|--------|
| `projects/broken_tool.py` | Modified | Fixed TypeError: converted values to `float()` in `monthly_total()` to handle string inputs |
| `reports/monthly-sales.md` | Created | Generated monthly sales summary per current procedure |
| `notes/workflow_log.md` | Created | Durable notes documenting the workflow for context preservation |

### Files Preserved (Unchanged)

| File | Reason |
|------|--------|
| `data/sales.csv` | Source data — must not be modified |
| `data/expenses.csv` | Source data — must not be modified |
| `notes/meeting_notes.md` | Source notes — must not be modified |
| `procedures/current.md` | Reference procedure — must not be modified |
| `procedures/previous.md` | Reference procedure — must not be modified |
| `README.md` | Workspace metadata — must not be modified |

### Changes Detail

1. **`projects/broken_tool.py`** — Added `float()` conversion in `monthly_total()` loop and initialized `total` as `0.0` instead of `0`. This fixes the `TypeError` that occurred when passing string numbers like `"30"`.

2. **`reports/monthly-sales.md`** — New report containing:
   - Validation results (header + numeric fields)
   - Total revenue: 580.0
   - Total units: 41
   - Per-product breakdown (A: 30 units/300.0, B: 9 units/180.0, C: 2 units/100.0)
   - Full transaction table
   - Review notes documenting compliance with current procedure

3. **`notes/workflow_log.md`** — Durable workflow notes for context compaction across session boundaries.

### Validation Summary

All 19 requirements verified:
- Source data integrity (4 checks) ✅
- Deliverable correctness (4 checks) ✅
- Current procedure compliance (6 checks) ✅
- Broken tool fix (2 checks) ✅
- No unauthorized modifications (2 checks) ✅
