# Weekly Workspace Report — Evidence Summary

**Generated from:** `knowledge_003` workspace (2026-07-01 to 2026-07-31)

---

## 1. Expenses (Source: `data/expenses.csv`)

Six expense entries recorded in July 2026 across four categories:

| Category   | Items | Total    |
|------------|-------|----------|
| software   | Editor (×2), Cloud storage | $49.97 |
| office     | Notebook, Printer paper | $12.70 |
| travel     | Train | $28.40 |

**Total expenses: $91.07**

**Evidence-backed observation:** Software subscriptions are recurring (Editor appears on both 2026-07-01 and 2026-07-15), suggesting ongoing monthly costs.

---

## 2. Sales (Source: `data/sales.csv`)

Six sales transactions for three products (A, B, C) in July 2026:

| Product | Units Sold | Revenue |
|---------|------------|---------|
| A       | 30         | $300    |
| B       | 9          | $180    |
| C       | 2          | $100    |

**Total revenue: $580. Total units: 41**

**Evidence-backed observation:** Product A is the top seller by both units (30) and revenue ($300, 51.7% of total).

---

## 3. Meeting Actions (Source: `notes/meeting_notes.md`)

Three action items assigned on 2026-07-31:

1. **Francesco** — review software subscriptions before next month.
2. **Marta** — prepare the July sales summary.
3. **Luca** — update the current operating procedure after the meeting.

Decisions recorded:
- Keep the cloud storage subscription.
- Review recurring software costs monthly.

**Evidence-backed observation:** The software subscription review (Francesco's task) aligns with the recurring Editor costs seen in the expense data ($19.99 × 2).

---

## 4. Procedure Evolution (Source: `procedures/current.md`, `procedures/previous.md`)

The monthly sales reporting procedure was updated. Key changes from previous to current:

| Aspect | Previous Procedure | Current Procedure |
|--------|-------------------|-------------------|
| Data validation | Not present | Step added: validate header and numeric fields |
| Metrics computed | Revenue only | Revenue **and** units |
| Output format | `reports/monthly-sales.txt` | `reports/monthly-sales.md` |
| Quality gate | None (send directly) | Mandatory review before sharing |

---

## 5. Broken Tool (Source: `projects/broken_tool.py`)

The file `projects/broken_tool.py` contains a `monthly_total()` function that will crash:

```python
def monthly_total(values):
    total = 0
    for value in values:
        total += value
    return total

if __name__ == "__main__":
    print(monthly_total([10, 20, "30"]))  # TypeError: int + str
```

**Evidence-backed observation:** The function receives a string `"30"` mixed with integers, causing a `TypeError` at runtime. This is an intentional fixture for debugging tasks.

---

## Cross-Topic Synthesis

- **Marta's task** (prepare the July sales summary) is directly supported by `data/sales.csv`. The current procedure (step 2–5) specifies how to produce this summary.
- **Francesco's task** (review software subscriptions) can be informed by `data/expenses.csv`, which shows recurring software costs of $49.97/month.
- **Luca's task** (update the current procedure) has already been completed — the procedure was updated between the previous and current versions, adding validation, unit calculation, Markdown output, and a review step.
- The broken tool in `projects/` is unrelated to the core weekly workflow but is available as a debugging exercise.
