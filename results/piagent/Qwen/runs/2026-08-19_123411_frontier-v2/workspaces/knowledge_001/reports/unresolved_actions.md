# Unresolved Actions Report

**Workspace:** knowledge_001  
**Analysis date:** 2026-08-19  
**Documents analysed:** 6 files across 4 directories

---

## Methodology

All business documents in the workspace were read and cross-referenced. Action items were extracted from meeting notes, procedures, and other artefacts. Duplicates and resolved decisions were removed. The three highest-priority unresolved actions are listed below. Missing deadlines are explicitly marked as **not specified** rather than guessed.

---

## Top 3 Unresolved Actions (Evidence Table)

| # | Action | Owner | Deadline | Priority | Source | Confidence |
|---|--------|-------|----------|----------|--------|------------|
| 1 | **Review software subscriptions** — Francesco must review all recurring software costs (Editor $19.99, Cloud storage $9.99) before next month, per the meeting decision to "review recurring software costs monthly." | Francesco | Not specified (deadline implied: end of August 2026 — "before next month" from 2026-07-31 meeting) | **High** | `notes/meeting_notes.md` — action item + Decisions section | High |
| 2 | **Prepare the July sales summary** — Marta must compile the monthly sales CSV, validate headers and numeric fields, calculate total revenue and units, and save the output as `reports/monthly-sales.md` following the current procedure (which adds a validation and review step missing from the previous procedure). | Marta | Not specified (implied: shortly after 2026-07-31 meeting; July data is complete as of 2026-07-29) | **High** | `notes/meeting_notes.md` — action item; `procedures/current.md` — required steps; `data/sales.csv` — source data | High |
| 3 | **Fix and run `projects/broken_tool.py`** — The script crashes because `"30"` is a string in the input list (`[10, 20, "30"]`), causing a TypeError during integer addition. The tool is needed to compute monthly totals per `procedures/current.md` step 3 ("Calculate total revenue and units"). | Not specified (owner unknown) | Not specified | **Medium** | `projects/broken_tool.py` — broken fixture; `procedures/current.md` — dependency | High |

---

## Deduplication & Resolved Items (Excluded)

The following items from the meeting notes were **not** included as unresolved because they are either resolved decisions or were merged into the actions above:

| Item | Source | Resolution |
|------|--------|------------|
| "Keep the cloud storage subscription for now" | `notes/meeting_notes.md` — Decisions | **Resolved** — decision recorded; no further action required beyond the monthly review (covered in Action #1). |
| "Update the current operating procedure after the meeting" — Luca | `notes/meeting_notes.md` — action item | **Likely resolved** — `procedures/current.md` appears to be the updated procedure (it adds validation, review step, and `.md` output format vs. `previous.md`). Luca has already acted. |
| "Review recurring software costs monthly" | `notes/meeting_notes.md` — Decisions | **Merged** into Action #1 (Francesco's subscription review). |

---

## Source Summary

| Document | Path | Relevance |
|----------|------|-----------|
| Weekly meeting notes | `notes/meeting_notes.md` | Extracted 3 action items + 2 decisions; primary source for owners and context. |
| Current procedure | `procedures/current.md` | Defines the 5-step workflow for monthly sales summary (validates, reviews, outputs `.md`). |
| Previous procedure | `procedures/previous.md` | Contrasted to confirm Luca's update task is resolved. |
| Expenses data | `data/expenses.csv` | 6 expense records (July 2026) — context for Action #1. |
| Sales data | `data/sales.csv` | 6 sales records (July 2026) — context for Action #2. |
| Broken tool | `projects/broken_tool.py` | Broken fixture — Action #3; needs type coercion fix for `"30"` → `30`. |

---

## Notes & Assumptions

- **Deadlines:** The meeting was held on 2026-07-31. "Before next month" for Francesco implies a deadline of end of August 2026. No explicit dates were given for Marta or the broken tool; these are marked **not specified**.
- **Confidence:** High confidence that the extracted items are genuine unresolved actions. Missing information (especially deadlines) was left as **not specified** rather than guessed.
- **Owner unknown:** Action #3 has no owner identified in the documents. The workspace README explicitly describes `broken_tool.py` as an "intentionally broken fixture for debugging tasks," so the owner depends on who is assigned debugging.
