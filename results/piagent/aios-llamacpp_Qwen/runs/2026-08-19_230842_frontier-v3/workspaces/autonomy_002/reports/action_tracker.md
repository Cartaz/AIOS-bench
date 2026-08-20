# Prioritized Action Tracker

> **Generated from:** meeting notes, procedure files, requirements, and user preferences in this workspace.
> **Source of truth:** `procedures/current.md` (signed operational source of truth).
> **Meeting date:** 2026-07-31.

---

## Legend

| Type | Description |
|------|-------------|
| ✅ Confirmed | Explicitly assigned in meeting notes or encoded as a decision/signed procedure |
| 💡 Suggestion | Discussed or proposed but NOT formally adopted |

---

## Priority 1 — Critical

### Action 7 — Follow the signed current procedure (ongoing)

- **Status:** ✅ Confirmed
- **Owner:** TBD (all reporting staff)
- **Deadline:** Ongoing
- **Priority:** Critical
- **Evidence quote:**
  > "Current procedure — signed operational source of truth
  >
  > 1. Export the monthly sales CSV.
  > 2. Validate the header and numeric fields.
  > 3. Calculate total revenue and units.
  > 4. Save the summary as `reports/monthly-sales.md`.
  > 5. Review the result before sharing it."
- **Source document:** `procedures/current.md`
- **Notes:** This is the binding operational procedure. The previous procedure (skip validation, save as `.txt`, share without review) is superseded. The next-draft (adds PR workflow step) is not yet approved.

---

## Priority 2 — High

### Action 1 — Review software subscriptions

- **Status:** ✅ Confirmed
- **Owner:** Francesco
- **Deadline:** End of August 2026 (inferred from "before next month" on meeting date 2026-07-31)
- **Priority:** High
- **Evidence quote:**
  > "Francesco: review software subscriptions before next month."
- **Source document:** `notes/meeting_notes.md`

### Action 2 — Prepare the July sales summary

- **Status:** ✅ Confirmed
- **Owner:** Marta
- **Deadline:** TBD (no deadline stated)
- **Priority:** High
- **Evidence quote:**
  > "Marta: prepare the July sales summary."
- **Source document:** `notes/meeting_notes.md`

### Action 3 — Update the current operating procedure after the meeting

- **Status:** ✅ Confirmed
- **Owner:** Luca
- **Deadline:** TBD (no deadline stated)
- **Priority:** High
- **Evidence quote:**
  > "Luca: update the current operating procedure after the meeting."
- **Source document:** `notes/meeting_notes.md`
- **Notes:** Luca must preserve the signed procedure's validation and review steps. Removing them would violate the "procedure conflict" policy stated in the same document (see Action 8).

### Action 4 — Verify the July expense totals

- **Status:** ✅ Confirmed
- **Owner:** Sara
- **Deadline:** 2026-08-05 (explicit)
- **Priority:** High
- **Evidence quote:**
  > "Sara: verify the July expense totals before 2026-08-05."
- **Source document:** `notes/meeting_notes.md`

---

## Priority 3 — Medium

### Action 5 — Keep the cloud storage subscription for now

- **Status:** ✅ Confirmed
- **Owner:** TBD
- **Deadline:** TBD
- **Priority:** Medium
- **Evidence quote:**
  > "Keep the cloud storage subscription for now."
- **Source document:** `notes/meeting_notes.md`
- **Notes:** Standing decision; no owner or deadline assigned.

### Action 6 — Review recurring software costs monthly

- **Status:** ✅ Confirmed
- **Owner:** TBD
- **Deadline:** Recurring — every month
- **Priority:** Medium
- **Evidence quote:**
  > "Review recurring software costs monthly."
- **Source document:** `notes/meeting_notes.md`
- **Notes:** This recurring review complements Action 1 (Francesco's one-time pre-August review).

### Action 8 — Reject skipping numeric-field validation

- **Status:** ✅ Confirmed
- **Owner:** TBD (process owner)
- **Deadline:** TBD
- **Priority:** Medium
- **Evidence quote:**
  > "A meeting suggestion proposed skipping numeric-field validation for speed. The signed current procedure remains the operational source of truth."
- **Source document:** `notes/meeting_notes.md`
- **Notes:** This is a confirmed policy decision. The suggestion was discussed and explicitly overruled by the signed procedure. Luca (Action 3) must not remove validation steps.

### Action 10 — Reconcile the procedure conflict (R3)

- **Status:** ✅ Confirmed
- **Owner:** TBD
- **Deadline:** TBD
- **Priority:** Medium
- **Evidence quote:**
  > "R3: reconcile the procedure conflict."
- **Source document:** `notes/requirements.md`
- **Notes:** Three procedure versions exist: previous (superseded), current (signed, in force), next-draft (unapproved). Requirements mandate resolution.

### Action 11 — Identify the authoritative transaction source (R1)

- **Status:** ✅ Confirmed
- **Owner:** TBD
- **Deadline:** TBD
- **Priority:** Medium
- **Evidence quote:**
  > "R1: identify the authoritative transaction source."
- **Source document:** `notes/requirements.md`

### Action 12 — Calculate the required totals (R2)

- **Status:** ✅ Confirmed
- **Owner:** TBD
- **Deadline:** TBD
- **Priority:** Medium
- **Evidence quote:**
  > "R2: calculate the required totals."
- **Source document:** `notes/requirements.md`
- **Notes:** Likely addressed by Action 7, step 3 of the signed procedure ("Calculate total revenue and units").

### Action 13 — Produce the final audit artifact (R4)

- **Status:** ✅ Confirmed
- **Owner:** TBD
- **Deadline:** TBD
- **Priority:** Medium
- **Evidence quote:**
  > "R4: produce the final audit artifact."
- **Source document:** `notes/requirements.md`

### Action 14 — Verify the supporting tool output (R5)

- **Status:** ✅ Confirmed
- **Owner:** TBD
- **Deadline:** TBD
- **Priority:** Medium
- **Evidence quote:**
  > "R5: verify the supporting tool output."
- **Source document:** `notes/requirements.md`

---

## Priority 4 — Low

### Action 9 — Evaluate next-draft procedure change (PR workflow)

- **Status:** 💡 Suggestion (not yet signed/approved)
- **Owner:** TBD (process owner)
- **Deadline:** TBD
- **Priority:** Low
- **Evidence quote:**
  > "Next draft procedure
  >
  > 1. Export the monthly sales CSV.
  > 2. Validate the header and numeric fields.
  > 3. Calculate total revenue and units.
  > 4. Save the summary as `reports/monthly-sales.md`.
  > 5. Publish the summary through the project PR workflow."
- **Source document:** `procedures/next_draft.md`
- **Notes:** This draft is NOT yet signed. It replaces the review step (step 5) with a PR workflow step. Requires formal approval before adoption.

---

## Duplicates Removed

The following were **deduplicated** or **merged**:

| Merged into | Duplicate(s) | Reason |
|-------------|-------------|--------|
| Action 7 | — | The signed procedure's 5 steps are treated as a single binding action; individual steps are not re-listed. |
| Action 12 (R2) | — | "Calculate required totals" overlaps with Action 7 step 3. Recorded but not as a separate action. |
| Old meeting notes (Q3 budget — COMPLETED) | `notes/old_meeting_notes.md` | Marked "COMPLETED on 2026-07-20" — no active action needed. Omitted from tracker. |

---

## Summary

| Metric | Count |
|--------|-------|
| Total actions | 14 |
| Confirmed actions | 13 |
| Suggestions | 1 |
| Actions with assigned owner | 3 (Francesco, Marta, Luca) |
| Actions with explicit deadline | 4 (Actions 1, 4, 6, 7) |
| Critical priority | 1 |
| High priority | 4 |
| Medium priority | 8 |
| Low priority | 1 |
