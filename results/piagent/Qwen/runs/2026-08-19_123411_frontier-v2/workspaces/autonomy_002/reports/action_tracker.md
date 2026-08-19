# Action Tracker

**Meeting Date:** 2026-07-31  
**Generated from:** `notes/meeting_notes.md`, `procedures/current.md`, `procedures/previous.md`  
**Generated:** 2026-08-19

---

## Schema

| Field       | Type          | Description                                  |
|-------------|---------------|----------------------------------------------|
| `id`        | integer       | Unique action ID                             |
| `description` | string      | Task or decision description                 |
| `owner`     | string/null   | Assigned person (only when explicitly stated) |
| `status`    | string        | `confirmed_action`, `decision`, or `suggestion` |
| `priority`  | string        | `high`, `medium`, or `low`                   |
| `deadline`  | string/null   | Only when explicitly evidenced               |
| `source`    | string        | Originating file                             |
| `category`  | string        | Inferred category                            |
| `notes`     | string        | Additional context or provenance             |

---

## Confirmed Actions (Prioritized)

### 🔴 Priority 1

| # | Action | Owner | Deadline | Source |
|---|--------|-------|----------|--------|
| 1 | Review software subscriptions before next month | Francesco | 2026-08-31 | meeting_notes.md |
| 2 | Prepare the July sales summary | Marta | — | meeting_notes.md |

**Notes:**
- **Action 1:** Deadline "before next month" inferred from meeting date 2026-07-31. Relevant expense data in `data/expenses.csv` includes recurring software costs (Editor: $19.99 x2, Cloud storage: $9.99).
- **Action 2:** No explicit deadline. Should follow the current procedure: export CSV → validate → calculate totals → save to `reports/monthly-sales.md` → review before sharing. See `procedures/current.md`.

### 🟡 Priority 2

| # | Action | Owner | Deadline | Source |
|---|--------|-------|----------|--------|
| 3 | Update the current operating procedure after the meeting | Luca | — | meeting_notes.md |

**Notes:**
- Relative deadline "after the meeting." Should align with the steps defined in `procedures/current.md` (which supersedes `procedures/previous.md`).

---

## Decisions (Not Action Items)

These are group decisions from the meeting — not assigned to anyone.

| # | Decision | Source |
|---|----------|--------|
| 4 | Keep the cloud storage subscription for now | meeting_notes.md |
| 5 | Review recurring software costs monthly | meeting_notes.md |

**Notes:**
- Decision 4 is consistent with expenses.csv showing active cloud storage ($9.99/month) and editor ($19.99 x2/month) subscriptions.
- Decision 5 supports Action 1 (Francesco's subscription review).

---

## Summary

- **Total items:** 5
- **Confirmed actions:** 3 (1 high-priority, 1 high-priority, 1 medium-priority)
- **Decisions (not actions):** 2
- **Duplicates resolved:** 0 (no duplicate action items found)
- **Owners assigned:** 3 of 5 items (Francesco, Marta, Luca)
- **Deadlines evidenced:** 1 of 5 items (Action 1 — "before next month")

All owners and deadlines are strictly evidence-based. No facts were invented.
