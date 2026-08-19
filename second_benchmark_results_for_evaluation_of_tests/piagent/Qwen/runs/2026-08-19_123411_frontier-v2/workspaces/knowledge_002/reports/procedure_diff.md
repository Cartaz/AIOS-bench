# Procedure Diff Report

**Source documents:**
- Previous procedure: `procedures/previous.md`
- Current procedure: `procedures/current.md`

---

## Summary

The current procedure (5 steps) is a **superset** of the previous procedure (4 steps) with two substantive changes and one step addition. One step was removed, one step was added, one step was modified, and one step was unchanged.

---

## Changes

### 1. Step 2 — Changed rule: added field validation

|                | Previous                                      | Current                                          |
|----------------|-----------------------------------------------|--------------------------------------------------|
| Step 2 text    | `Calculate total revenue.`                    | `Validate the header and numeric fields.`        |

- **Previous (`procedures/previous.md`, step 2):** Directly calculated total revenue from the exported CSV.
- **Current (`procedures/current.md`, step 3):** Replaces the calculation with a data-quality gate — the header and numeric fields must be validated before any calculations are performed.
- **Operator impact:** The new step introduces a mandatory validation checkpoint. If the CSV header or numeric fields fail validation, the process must stop or flag an error *before* any revenue calculation. This prevents garbage-in-garbage-out and adds an early-fail safety net.

### 2. Step 3 — Added rule: calculate total revenue and units

|                | Current (step 4)                              |
|----------------|-----------------------------------------------|
| Step 3 text    | `Calculate total revenue and units.`          |

- **Previous:** Revenue calculation was embedded in step 2.
- **Current:** The revenue calculation is now its own distinct step (step 4 in the current procedure), and it additionally computes **units** (a metric absent from the previous procedure entirely).
- **Operator impact:** Separating calculation from validation clarifies responsibilities and allows the validation failure path to short-circuit. The addition of "units" means the resulting summary now includes a quantity metric in addition to revenue, which was not previously required.

### 3. Step 4 — Changed output file format

|                | Previous                                          | Current                                              |
|----------------|---------------------------------------------------|------------------------------------------------------|
| Step 3/4 text  | `Save the summary as reports/monthly-sales.txt.`  | `Save the summary as reports/monthly-sales.md.`      |

- **Previous (`procedures/previous.md`, step 3):** Output was saved as a `.txt` file.
- **Current (`procedures/current.md`, step 4):** Output is saved as a `.md` (Markdown) file.
- **Operator impact:** The change from `.txt` to `.md` means the output is now formatted with Markdown, enabling richer rendering (headings, bold, lists) in downstream tools and viewers. This affects how downstream consumers read and potentially further process the summary.

### 4. Step 4 → Step 5 — Added rule: mandatory review step

|                | Previous                                          | Current                                              |
|----------------|---------------------------------------------------|------------------------------------------------------|
| Previous       | `Send the summary without a separate review step.`| `Review the result before sharing it.`               |

- **Previous (`procedures/previous.md`, step 4):** The summary was sent immediately with an explicit instruction to skip review.
- **Current (`procedures/current.md`, step 5):** Introduces a mandatory review step before the result is shared.
- **Operator impact:** This is a significant governance change. The previous procedure explicitly discouraged a review step ("without a separate review step"); the current procedure mandates one. This adds a quality-control checkpoint, potentially slowing delivery but reducing the risk of errors reaching stakeholders. The earlier step about sending the summary has been removed entirely, with the implicit expectation that review is the gate to sharing.

---

## Unchanged Sections

### Step 1 — Export the monthly sales CSV

|                | Text                                              |
|----------------|---------------------------------------------------|
| Previous       | `Export the monthly sales CSV.`                   |
| Current        | `Export the monthly sales CSV.`                   |

- **Status:** Identical in both procedures.
- **Operator impact:** No change to the initial data export action. The source of truth remains `data/sales.csv`.

---

## Structural Overview

| # | Previous step                        | Current step                           | Change type |
|---|--------------------------------------|----------------------------------------|-------------|
| 1 | Export the monthly sales CSV.        | Export the monthly sales CSV.          | Unchanged   |
| 2 | Calculate total revenue.             | Validate the header and numeric fields.| Changed     |
| 3 | Save the summary as .txt.            | Calculate total revenue and units.     | Replaced    |
| 4 | Send without review.                 | Save the summary as .md.               | Replaced    |
| – | –                                    | Review before sharing.                 | Added       |

- **Total steps:** Previous = 4 → Current = 5
- **Additions:** 1 (review step)
- **Removals:** 1 (explicit "send without review" instruction)
- **Modifications:** 2 (validation addition, file format change)
