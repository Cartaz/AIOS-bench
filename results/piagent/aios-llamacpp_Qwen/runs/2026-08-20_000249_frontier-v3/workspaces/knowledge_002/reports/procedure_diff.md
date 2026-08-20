# Procedure Diff Report

**Files compared:**
- `procedures/previous.md` (5 lines)
- `procedures/current.md` (7 lines)
- `procedures/next_draft.md` (5 lines)

---

## 1. Additions (present in current/next but absent in previous)

### Addition 1: Header and field validation (new step 2)
- **Files:** `procedures/current.md:2`, `procedures/next_draft.md:2`
- **Text:** "Validate the header and numeric fields."
- **Previous state:** Step 2 in `procedures/previous.md:2` was "Calculate total revenue" — no validation existed.
- **Operator impact:** Reduces risk of processing malformed CSV data. Adds a manual or automated gate before computation, increasing the operator's workload slightly but improving data integrity.

### Addition 2: "and units" to revenue calculation
- **Files:** `procedures/current.md:3`, `procedures/next_draft.md:3`
- **Text:** "Calculate total revenue and units." (vs. `procedures/previous.md:2`: "Calculate total revenue.")
- **Operator impact:** Operator must now also compute a units metric. Slightly more work per run, but produces richer output.

---

## 2. Removals / Changes (absent from or altered from previous)

### Removal 1: "Send the summary without a separate review step"
- **File:** `procedures/previous.md:4`
- **Status:** **Removed entirely** in both `current.md` and `next_draft.md`.
- **Impact:** The previous procedure had no quality gate. Both successors add a review/publish step, tightening operational control.

### Removal 1b: `.txt` output extension
- **File:** `procedures/previous.md:3` — "Save the summary as `reports/monthly-sales.txt`."
- **Changed to:** `procedures/current.md:4` and `procedures/next_draft.md:4` — "Save the summary as `reports/monthly-sales.md`."
- **Operator impact:** Output is now Markdown instead of plain text. Operators using downstream Markdown-aware tools will benefit; plain-text consumers will need adjustment.

---

## 3. Unchanged Sections

### Step 1: Export the monthly sales CSV
- **previous.md:1**, **current.md:1**, **next_draft.md:1** — Identical. No change.

### Steps 2–4 (current ↔ next): Validation, calculation, and save
- Steps 1–4 in `procedures/current.md` (lines 1–4) are **identical** to the corresponding steps in `procedures/next_draft.md` (lines 1–4). These four steps are stable across both newer versions.

---

## 4. Changes specific to next_draft (current → next_draft)

### Change 1: Review → Publish through PR workflow
- **current.md:5:** "Review the result before sharing it."
- **next_draft.md:5:** "Publish the summary through the project PR workflow."
- **Impact:** Replaces a general review-then-share step with a structured pull-request workflow. This introduces version control discipline and peer review, changing the operator's workflow from a direct review-and-share to a PR-based publish cycle. It is a meaningful procedural shift that adds collaboration overhead but improves traceability.

---

## 5. Summary of Differences

| Aspect | previous.md → current.md | current.md → next_draft.md |
|--------|-------------------------|---------------------------|
| Validation step | **Added** (new step 2) | Unchanged |
| Revenue calc | **Changed:** "total revenue" → "total revenue and units" | Unchanged |
| Output format | **Changed:** `.txt` → `.md` | Unchanged |
| Review/Publish | **Added** review step | **Replaced** review with PR workflow |
| Old "send without review" | **Removed** | N/A (already gone) |

---

## 6. Net Assessment

The evolution from `previous.md` to `current.md` introduced **two** major improvements (data validation and review gating) plus a format change (`.txt` → `.md`). The further evolution from `current.md` to `next_draft.md` makes a **single substantive change**: replacing an informal review-and-share step with a formal PR-based publish workflow. No steps were removed between `current.md` and `next_draft.md`; the change is a direct replacement of step 5.
