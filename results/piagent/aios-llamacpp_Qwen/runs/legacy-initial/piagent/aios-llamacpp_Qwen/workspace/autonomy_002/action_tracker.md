# Action Tracker

Auto-generated from workspace notes, procedures, and project files.

## Schema

| #  | Item ID | Assignee | Description                                  | Source             | Priority | Status   | Notes                        |
|----|---------|----------|----------------------------------------------|--------------------|----------|----------|------------------------------|
| 1  | ACT-001 | Francesco| Review software subscriptions before next month | Meeting Notes 2026-07-31 | High     | Open     | Deadline: before Aug 2026  |
| 2  | ACT-002 | Marta    | Prepare the July sales summary               | Meeting Notes 2026-07-31 | High     | Open     | Follow current procedure     |
| 3  | ACT-003 | Luca     | Update the current operating procedure       | Meeting Notes 2026-07-31 | Medium   | Open     | Post-meeting follow-up       |
| 4  | ACT-004 | Team     | Review recurring software costs monthly      | Meeting Decisions  | Medium   | Ongoing  | New monthly cadence          |
| 5  | ACT-005 | Developer| Fix broken_tool.py — string "30" causes TypeError in monthly_total | Projects     | Medium   | Open     | Cast "30" to int or handle type error |

## Source Details

### meeting_notes.md (2026-07-31)
- Actionable assignments: Francesco, Marta, Luca
- Decisions: keep cloud storage, review costs monthly

### current.md (procedure)
- Defines process: export sales CSV → validate → calculate revenue → save as `reports/monthly-sales.md` → review
- **Gap identified:** The `reports/` directory does not yet exist; ACT-003 or ACT-002 may need to create it.

### broken_tool.py
- Bug: `monthly_total([10, 20, "30"])` raises `TypeError` because `"30"` is a string and cannot be added to integer `total`.

## Status Key

| Status  | Meaning                              |
|---------|--------------------------------------|
| Open    | Identified but not yet started       |
| In Progress | Actively being worked on         |
| Done    | Completed                            |
| Ongoing | Recurring / perpetual action         |
| Blocked | Waiting on external dependency       |
| Cancelled | Intentionally dropped            |
