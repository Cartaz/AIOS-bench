# Comparative Report — July 2026 Workspace Analysis

> Generated from: `data/expenses.csv`, `data/sales.csv`, `notes/meeting_notes.md`, `procedures/current.md`, `procedures/previous.md`, `projects/broken_tool.py`

---

## 1. Expenses Analysis

| Category    | # Items | Total (€) | Share  |
|-------------|---------|-----------|--------|
| Software    | 3       | 49.97     | 54.9%  |
| Travel      | 1       | 28.40     | 31.2%  |
| Office      | 2       | 12.70     | 14.0%  |
| **Total**   | **6**   | **91.07** | **100%**|

**Key observations:**
- Software is the dominant expense category (54.9%), with two identical editor subscriptions (€19.99 each) and one cloud storage fee (€9.99).
- The meeting notes (2026-07-31) flag this concern: "review software subscriptions before next month" — the duplicate editor purchases on 2026-07-01 and 2026-07-15 suggest possible redundant licensing.
- The meeting decision to "review recurring software costs monthly" aligns with this finding.
- Travel (train, €28.40) and office supplies (notebook + printer paper, €12.70) are comparatively minor.

---

## 2. Sales Analysis

| Product | Transactions | Units | Revenue (€) | Avg Price/Unit (€) |
|---------|-------------|-------|-------------|--------------------|
| A       | 3           | 30    | 300         | 10.00              |
| B       | 2           | 9     | 180         | 20.00              |
| C       | 1           | 2     | 100         | 50.00              |
| **Total** | **6**     | **41**| **580**     | **14.15**          |

**Key observations:**
- Product A is the volume leader (30 units, 3 transactions) but the cheapest per unit (€10.00), generating 51.7% of total revenue.
- Product B has fewer units (9) but commands double the price (€20.00/unit), contributing 31.0% of revenue.
- Product C is a premium item (€50.00/unit) with only one transaction (2 units = €100, 17.2% of revenue).
- Overall average price per unit is €14.15, heavily weighted downward by Product A's volume.
- The meeting assigned Marta to "prepare the July sales summary" — this report fulfills that action item.

---

## 3. Procedure Comparison: Previous vs. Current

| Step | Previous Procedure                  | Current Procedure                         | Change                        |
|------|-------------------------------------|-------------------------------------------|-------------------------------|
| 1    | Export monthly sales CSV            | Export monthly sales CSV                  | *Unchanged*                   |
| 2    | Calculate total revenue             | **Validate** header & numeric fields, then calculate revenue **and units** | Validation added; units tracking added |
| 3    | Save as `reports/monthly-sales.txt` | Save as `reports/monthly-sales.md`        | Format upgraded to Markdown   |
| 4    | Send without review                 | **Review** result before sharing          | Quality gate added            |

### Assessment

The current procedure is a clear improvement over the previous one in three respects:

1. **Data integrity**: The new validation step catches malformed headers or non-numeric fields before aggregation — a critical safeguard given that the `broken_tool.py` demonstrates a `TypeError` when non-numeric strings enter the computation pipeline.
2. **Completeness**: Tracking units alongside revenue gives a fuller picture (as shown in Section 2), enabling per-unit pricing analysis.
3. **Output quality**: Markdown output is more portable and readable than plain text, and the mandatory review step prevents errors from reaching stakeholders.

The meeting notes instruct Luca to "update the current operating procedure after the meeting" — the current procedure reflects this update.

---

## 4. Broken Tool Analysis (`projects/broken_tool.py`)

The `monthly_total` function contains a type-safety bug:

```python
def monthly_total(values):
    total = 0
    for value in values:
        total += value
    return total
```

**Bug**: When called with `monthly_total([10, 20, "30"])`, the third element (`"30"`) is a string, causing a `TypeError` on `total += value` (you cannot add `str` to `int`).

**Root cause**: The function assumes all inputs are numeric but performs no type checking or conversion.

**Relation to procedure**: This bug underscores why the current procedure's validation step (Step 2) is essential. If sales/expense data containing non-numeric values flowed through this tool, it would crash silently or corrupt results. The previous procedure lacked validation precisely because there was no mechanism to catch such issues.

**Fix suggestion**: Convert values to float/int or validate types:
```python
def monthly_total(values):
    return sum(float(v) for v in values)
```

---

## 5. Cross-Document Reconciliation

| Claim / Action Item               | Source                         | Status / Verification              |
|-----------------------------------|--------------------------------|------------------------------------|
| "Review software subscriptions"  | Meeting notes                  | Confirmed: 2x editor, 1x cloud storage — total €49.97 software spend |
| "Keep cloud storage subscription" | Meeting notes                  | No conflicting data found; decision stands |
| "Review recurring software costs monthly" | Meeting notes       | Current procedure's validation step supports this goal |
| "Prepare July sales summary"     | Meeting notes                  | This report fulfills that action   |
| "Update current procedure"        | Meeting notes (Luca)           | Current procedure reflects updated process |
| Sales total = 580                 | This report                    | Confirmed by raw data: 100+80+120+100+100+80 |
| Expenses total = 91.07            | This report                    | Confirmed by raw data: 19.99+9.99+4.50+19.99+28.40+8.20 |

**No conflicting claims detected.** All documents are internally consistent and mutually reinforcing.

---

## Summary

1. **Expenses** total €91.07 in July, dominated by software (54.9%). The meeting's directive to review subscriptions is warranted.
2. **Sales** generated €580 from 41 units across 3 products. Product A drives volume; Product C drives margin.
3. **The current procedure** is a meaningful improvement over the previous one: it adds validation, unit tracking, markdown formatting, and a mandatory review step.
4. **The broken tool** (`broken_tool.py`) is a type-safety vulnerability that the new validation step in the current procedure is designed to prevent.
5. **All meeting action items** from the 2026-07-31 meeting are addressed or fulfilled by this analysis.
