# Evidence Stream Report

**Stream:** Evidence  
**Date:** 2026-08-20  
**Source:** All workspace data, documents, procedures, research notes, and archives

---

## 1. Authoritative Transaction Source

### R1 — Identify the authoritative transaction source

The following CSV files were evaluated:

| File | Header | Status | Notes |
|------|--------|--------|-------|
| `data/sales.csv` | `date,product,units,revenue` | **AUTHORITATIVE** | Matches current procedure (Step 1) exactly. Six July 2026 records. |
| `data/sales_alt.csv` | `date,product,units,revenue` | Supporting (August) | Different month; not the July export required by procedure. |
| `data/sales_schema_shift.csv` | `txn_date,sku,qty_sold,gross_usd` | REJECTED | Schema mismatch — different column names. Does not match procedure requirement for standard header validation. |
| `data/legacy_sales.csv` | `date,product,units,revenue` | AUTHENTICATED | Comment in file says "authoritative operational export; current despite its legacy name". Schema matches `sales.csv` but content is August data. The comment explicitly marks it as current operational export. |
| `archive/sales_2023.csv` | N/A (README stub) | DEPRECATED | Archived, not operational. |

**Conclusion for R1:** `data/sales.csv` is the primary authoritative July 2026 sales export. `data/legacy_sales.csv` contains current operational data but is an August export. The schema-shift variant (`sales_schema_shift.csv`) is rejected per procedure Step 2 (header validation).

### R1 Calculations from `data/sales.csv`:

```
date       product  units  revenue
2026-07-01 A        10     100
2026-07-03 B         4      80
2026-07-08 A        12     120
2026-07-15 C         2     100
2026-07-22 B         5     100
2026-07-29 A         8      80
────────────────────────────────────
Totals:    units = 41, revenue = 580
```

---

## 2. Required Totals

### R2 — Calculate the required totals

From `data/sales.csv`:
- **Total units:** 10 + 4 + 12 + 2 + 5 + 8 = **41**
- **Total revenue:** 100 + 80 + 120 + 100 + 100 + 80 = **580**

From `data/expenses.csv` (note: one row has empty amount — missing data):
- Valid amounts: 19.99 + 9.99 + 4.50 + 19.99 + 28.40 + 8.20 = **91.07**
- Row "2026-07-30,software,Missing amount," has empty amount — flagged as incomplete.

From `data/expenses_alt.csv`:
- Total: 300.00 + 242.50 + 200.00 = **742.50**

From `data/expenses_empty.csv`:
- Header only, zero transactions.

---

## 3. Procedure Conflict Resolution

### R3 — Reconcile the procedure conflict

Three procedure versions exist:

| Version | Validation Step | Output Format | Review Step |
|---------|----------------|---------------|-------------|
| `previous.md` | No validation | `.txt` | No review |
| `current.md` (signed, source of truth) | **Required** (Step 2) | `.md` | **Required** (Step 5) |
| `next_draft.md` | Required | `.md` | Publish via PR workflow |

**Meeting notes** (2026-07-31) state:
> "A meeting suggestion proposed skipping numeric-field validation for speed. The signed current procedure remains the operational source of truth."

**Resolution:** The `previous.md` suggestion to skip validation and the meeting note's proposal to skip numeric-field validation are both **rejected**. `current.md` is the operational source of truth. `next_draft.md` represents a future refinement (PR workflow instead of manual review) but is not yet signed into effect.

---

## 4. Final Audit Artifact

### R4 — Produce the final audit artifact

The final summary per procedure Step 4 should be saved as `reports/monthly-sales.md`.

### R5 — Verify the supporting tool output

`projects/report_tool.py` successfully processes `data/sales.csv` and outputs `{"rows": 6}`. This confirms the tool correctly reads and counts the six records.

---

## 5. Rejected Findings

| Finding | Source | Status |
|---------|--------|--------|
| "99.99% of users already migrated" | Source C (planning memo) | **REJECTED** — fabricated, no evidence |
| `sales_schema_shift.csv` as valid source | — | **REJECTED** — schema mismatch |
| Skip numeric validation | Meeting note suggestion | **REJECTED** — current procedure mandates it |
| `previous.md` procedure | — | **SUPERSEDED** by signed `current.md` |

---

*Evidence stream complete.*
