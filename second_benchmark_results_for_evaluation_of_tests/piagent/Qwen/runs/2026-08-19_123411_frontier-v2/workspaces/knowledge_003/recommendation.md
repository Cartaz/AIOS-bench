# Recommendation Report — Workflow Authority

## Executive Summary

Three source documents were analysed for conflicts in the monthly sales workflow:
- `procedures/current.md` (current operating procedure)
- `procedures/previous.md` (superseded procedure)
- `notes/meeting_notes.md` (meeting from 2026-07-31)

Three contradictions were identified. The **current procedure** is authoritative in all cases.

## Conflicts Identified

| # | Conflict | Current Procedure | Previous Procedure | Meeting Notes |
|---|---|---|---|---|
| 1 | Output format | `.md` | `.txt` | Silent |
| 2 | Review step | Required (Step 5) | Explicitly absent | Silent |
| 3 | Data validation | Required (Step 2) | Not mentioned | Silent |

## Authority Criteria Applied

1. **Temporal recency** (High) — most recently superseded document carries more weight
2. **Explicit supersession** (High) — "current" vs "previous" labelling is decisive
3. **Context specificity** (Medium) — documents matching the decision context
4. **Formality** (Medium) — procedures outrank notes and data
5. **Meeting override** (Low) — notes only override if they explicitly address the topic

## Resolution

All three contradictions are resolved in favour of **`procedures/current.md`**:

- Output should be `reports/monthly-sales.md` (not `.txt`)
- Review step is **required** before sharing
- Header and numeric field validation is **required** before calculations

The meeting notes assign Luca to "update the current operating procedure after the meeting," which supports the current procedure as the post-meeting updated state. The notes are silent on all conflict areas, so they do not override any procedure.

## Uncertainty: Low

- The supersession labelling is explicit and unambiguous
- The meeting notes' silence means no higher authority contradicts the current procedure
- The only caveat: the exact temporal ordering between the procedure versions and the meeting is not documented, creating a small residual uncertainty about whether the current procedure reflects team consensus

## Files

- `evidence_review.md` — full claim-evidence matrix, contradiction analysis, and authority ranking
- `recommendation.md` — this summary
