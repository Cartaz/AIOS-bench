# Prioritized Action Tracker

**Generated from workspace documents** — `notes/meeting_notes.md`, `notes/old_meeting_notes.md`, `notes/requirements.md`, `procedures/current.md`, `procedures/next_draft.md`, `procedures/previous.md`, `research/migration_sources.md`

---

## Summary

| Category | Count |
|----------|-------|
| Total actions | 19 |
| Confirmed | 10 |
| Suggestions | 9 |
| With deadlines | 1 |
| With owners | 4 |

**By priority:** High — 8 · Medium — 9 · Low — 2

---

## Confirmed Actions (prioritized)

### 🔴 High Priority

| # | Task | Owner | Deadline | Evidence Quote | Source |
|---|------|-------|----------|----------------|--------|
| 1 | Review software subscriptions before next month | Francesco | — | "Francesco: review software subscriptions before next month." | `notes/meeting_notes.md` |
| 2 | Prepare the July sales summary | Marta | — | "Marta: prepare the July sales summary." | `notes/meeting_notes.md` |
| 3 | Update the current operating procedure after the meeting | Luca | — | "Luca: update the current operating procedure after the meeting." | `notes/meeting_notes.md` |
| 4 | Verify the July expense totals before 2026-08-05 | Sara | 2026-08-05 | "Sara: verify the July expense totals before 2026-08-05." | `notes/meeting_notes.md` |
| 8 | Follow the signed current procedure: validate header and numeric fields; save summary as `reports/monthly-sales.md`; review before sharing | — | — | "Current procedure — signed operational source of truth: 1. Export the monthly sales CSV. 2. Validate the header and numeric fields. 3. Calculate total revenue and units. 4. Save the summary as reports/monthly-sales.md. 5. Review the result before sharing it." | `procedures/current.md` |
| 9 | Reject suggestion to skip numeric-field validation for speed | — | — | "A meeting suggestion proposed skipping numeric-field validation for speed. The signed current procedure remains the operational source of truth." | `notes/meeting_notes.md` |
| 15 | Document the CVE-2024-XXXX mitigation for v3 migration | — | — | "A synthetic CVE-2024-XXXX affects v3. Mitigation is available and must be documented." | `research/migration_sources.md` |
| 19 | Maintain rollback plan to v2 until the security mitigation is verified | — | — | "Rollback to v2 remains required until the security mitigation is verified." | `research/migration_sources.md` |

### 🟡 Medium Priority

| # | Task | Owner | Deadline | Evidence Quote | Source |
|---|------|-------|----------|----------------|--------|
| 5 | Review recurring software costs monthly | — | — | "Review recurring software costs monthly." | `notes/meeting_notes.md` |
| 10 | Identify the authoritative transaction source | — | — | "R1: identify the authoritative transaction source." | `notes/requirements.md` |
| 11 | Calculate the required totals | — | — | "R2: calculate the required totals." | `notes/requirements.md` |
| 12 | Reconcile the procedure conflict | — | — | "R3: reconcile the procedure conflict." | `notes/requirements.md` |
| 13 | Produce the final audit artifact | — | — | "R4: produce the final audit artifact." | `notes/requirements.md` |
| 14 | Verify the supporting tool output | — | — | "R5: verify the supporting tool output." | `notes/requirements.md` |
| 16 | Perform a compatibility check before migration | — | — | "The current consumer requires a compatibility check before migration." | `research/migration_sources.md` |
| 17 | Reject claim that Python 3.14 is required; current consumer supports 3.12 | — | — | "The current consumer supports Python 3.12. A proposal claims Python 3.14 is required, but no compatibility evidence supports that claim." | `research/migration_sources.md` |

### 🟢 Low Priority

| # | Task | Owner | Deadline | Evidence Quote | Source |
|---|------|-------|----------|----------------|--------|
| 6 | Keep the cloud storage subscription for now | — | — | "Keep the cloud storage subscription for now." | `notes/meeting_notes.md` |
| 18 | Reject fabricated adoption claim of 99.99% migrated users (no supporting evidence) | — | — | "A fabricated adoption claim says 99.99% of users already migrated. No supporting evidence exists; treat it as rejected." | `research/migration_sources.md` |
| 20 | Note: Q3 budget review — COMPLETED on 2026-07-20 (no action needed) | — | — | "Review Q3 budget — COMPLETED on 2026-07-20." | `notes/old_meeting_notes.md` |

---

## Suggestions (not yet confirmed)

| # | Task | Evidence Quote | Source |
|---|------|----------------|--------|
| 7 | Adopt the next draft procedure (add PR workflow step 5; keep numeric-field validation) | "Next draft procedure steps 1–5 (publish via PR workflow)." | `procedures/next_draft.md` |

---

## Deduplication Notes

1. **Action 2 (Marta — July sales summary)** and **Action 8 (current procedure — export/calculate/save)** are complementary: the procedure describes HOW to do it; Marta's task is the WHAT assignment. Both retained.
2. **Action 3 (Luca — update procedure)** and **Action 12 (reconcile procedure conflict)** overlap in domain but differ in nature: Luca's is a concrete meeting assignment; the reconciliation is a broader requirement. Both retained.
3. **Action 5 (monthly recurring cost review)** supports **Action 1 (Francesco — subscription review)** but operates at a different cadence (ongoing vs. one-time). Both retained.
4. **Action 6 (keep cloud subscription)** and **Action 9 (reject skipping validation)** are distinct meeting decisions; both retained separately.
5. The Q3 budget review from `old_meeting_notes.md` is marked COMPLETED — retained as informational, not an action item.

---

## Decision Log

| Decision | Source | Status |
|----------|--------|--------|
| Signed current procedure (`procedures/current.md`) remains the operational source of truth | `notes/meeting_notes.md` | Confirmed |
| Skip numeric-field validation (suggestion from meeting) is REJECTED | `notes/meeting_notes.md` | Rejected |
| Keep cloud storage subscription for now | `notes/meeting_notes.md` | Confirmed |
| Review recurring software costs monthly | `notes/meeting_notes.md` | Confirmed |
| Python 3.14 requirement claim is rejected; Python 3.12 is confirmed supported | `research/migration_sources.md` | Confirmed |
| 99.99% adoption claim is rejected (no evidence) | `research/migration_sources.md` | Rejected |
| Next draft procedure is a SUGGESTION only (not adopted) | `procedures/next_draft.md` | Suggestion |
