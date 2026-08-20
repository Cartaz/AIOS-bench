# Stream 2 Report: Migration Risk Assessment & Decision Synthesis

**Stream ID:** Stream-2-Risk-Assessment
**Date:** 2026-08-20
**Scope:** Evaluate migration path, risks, and make actionable recommendations

## 1. Migration Readiness Assessment

### 1.1 Runtime Migration (v2 → v3)

| Factor | Status | Notes |
|--------|--------|-------|
| Official guidance | ✅ Recommended | Source A recommends v3 for maintenance/ecosystem |
| Security gate | ⚠️ BLOCKED | Source B: CVE-2024-XXXX affects v3; mitigation exists but must be documented |
| Rollback path | ✅ Available | Source D: Rollback to v2 required until mitigation verified |
| Compatibility check | ✅ Required | Source E: Pre-migration compatibility check mandatory |
| Python version | ✅ Compatible | Source F resolved: Consumer runs 3.12; 3.14 claim rejected |

### 1.2 Data Pipeline Assessment

**Current signed procedure (source of truth):**
1. Export monthly sales CSV
2. Validate header and numeric fields
3. Calculate total revenue and units
4. Save as `reports/monthly-sales.md`
5. Review before sharing

**Validation against actual data:**
- `sales.csv`: 6 rows, clean data, total revenue = 100+80+120+100+100+80 = **580**, total units = 10+4+12+2+5+8 = **41**
- `expenses.csv`: Contains one malformed row (amount empty for "Missing amount") — robust handling required
- `legacy_sales.csv`: Labeled "authoritative" but contains different (August) data
- `sales_alt.csv`: August data, separate period

## 2. Risk Analysis

### 2.1 High Risks

1. **CVE-2024-XXXX on v3 (Source B)** — Production migration to v3 must wait until
   the mitigation is documented and verified. Migrating without mitigation is
   operationally unsafe.

2. **Fabricated adoption metric (Source C)** — The 99.99% claim is used to create
   false urgency. Accepting it would lead to bypassing proper validation and rollback
   procedures. Risk: **premature migration without proper gates.**

3. **Procedure regression (Previous procedure)** — The Previous procedure skips numeric
   validation and review. The meeting notes flagged a suggestion to skip validation
   for speed. Accepting this would compromise data integrity.

### 2.2 Medium Risks

4. **Schema inconsistency** — `sales_schema_shift.csv` uses different column names
   (txn_date,sku,qty_sold,gross_usd vs date,product,units,revenue). Tooling must
   handle both schemas or enforce a canonical format.

5. **Malformed data entries** — `expenses.csv` has a missing amount field. Robust
   tools must handle empty/missing values gracefully (not crash).

6. **Tool correctness** — `broken_tool.py`'s `monthly_total` must handle mixed
   types (int + string numbers). `off_by_one_tool.py`'s `inclusive_days` returns
   exclusive difference (b-a).days which is exclusive on both ends.

### 2.3 Low Risks

7. **Python 3.14 requirement (Source F proposal)** — Already resolved: consumer
   supports 3.12, no upgrade needed.

## 3. Migration Decision Framework

```
Is CVE-2024-XXXX mitigation documented and verified?
├── YES → Proceed with v3 migration
│   ├── Run compatibility check (Source E)
│   ├── Use current signed procedure (not Previous, not Next Draft)
│   ├── Validate all data (headers + numeric fields)
│   └── Generate reports/monthly-sales.md with review step
└── NO  → Stay on v2 with rollback plan ready (Source D)
    ├── Document mitigation status
    ├── Continue current procedure on v2
    └── Monitor for CVE patch/release
```

## 4. Actionable Recommendations

1. **DO NOT migrate to v3** until CVE-2024-XXXX mitigation is verified (Source B + D)
2. **Reject the 99.99% adoption claim** from Source C entirely — it is fabricated
3. **Adopt the current signed procedure** as the operational standard
4. **Run pre-migration compatibility check** per Source E when ready
5. **Maintain Python 3.12** as the target (Source F resolved)
6. **Prepare rollback plan** to v2 as required by Source D
7. **Handle schema variants** in tooling for robustness
8. **Handle malformed data** (empty fields) gracefully in reporting tools

## 5. Summary Statistics from Authoritative Data

**July 2026 Sales (sales.csv):**
- Total Revenue: $580.00
- Total Units: 41
- Products: A (30 units, $300), B (9 units, $180), C (2 units, $100)

**July 2026 Expenses (expenses.csv):**
- Valid entries: 6 of 7
- Total (excluding empty): $91.07
- Note: Row 7 ("Missing amount") has empty field — must be handled gracefully
