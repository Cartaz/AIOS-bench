# Evidence Review — Authoritative Workflow Determination

## Executive Summary

The authoritative workflow is **`procedures/current.md`**. This determination is based on explicit textual designation within the documents themselves.

## Authoritative Source

**`notes/meeting_notes.md`** (dated 2026-07-31) explicitly states:

> "A meeting suggestion proposed skipping numeric-field validation for speed. The signed current procedure remains the operational source of truth."

This single sentence resolves all procedure conflicts by naming `procedures/current.md` as the operative standard. The meeting notes also serve as the governing meeting record, as the older meeting notes (`notes/old_meeting_notes.md`) contain only a single completed budget review item and no procedure discussions.

## Criteria for Authoritativeness

The following criteria were applied, in order of weight:

1. **Explicit designation**: `notes/meeting_notes.md` directly names `current.md` as "the signed current procedure" and "the operational source of truth." This is the strongest evidence.
2. **Document labeling**: File names provide strong meta-evidence:
   - `previous.md` → labeled "Previous procedure" — explicitly superseded.
   - `current.md` → labeled "Current procedure — signed operational source of truth" — self-identified as authoritative, confirmed by meeting notes.
   - `next_draft.md` → labeled "Next draft procedure" — explicitly a draft, not yet approved.
3. **Chronology**: Meeting notes dated 2026-07-31 reference the current procedure as the standing standard, placing it after the previous procedure and before any adoption of the next draft.
4. **Consistency**: The current procedure (5 steps) is internally consistent and addresses concerns raised in the meeting (numeric-field validation retained despite speed concerns).

## Key Claims and Conflicting Sources

| Claim | Authoritative Source (current.md) | Contradicting Source | Nature of Conflict |
|---|---|---|---|
| Validate header and numeric fields? | Yes (step 2) | previous.md: No validation step; meeting_notes.md: a suggestion to skip was rejected | previous.md is superseded |
| Output format | `.md` (step 4) | previous.md: `.txt`; next_draft.md: `.md` (agrees on .md but not authoritative) | previous.md is superseded |
| Review step required? | Yes (step 5) | previous.md: explicitly "without a separate review step" | previous.md is superseded |
| Calculate units in addition to revenue? | Yes (step 3) | previous.md: "total revenue" only | previous.md is superseded |
| Publish via PR workflow? | No (not in current) | next_draft.md: step 5 requires PR publishing | next_draft is unapproved |

## Uncertainty

- **Low uncertainty** on the core determination: `notes/meeting_notes.md` is unambiguous in naming `current.md` as the authoritative source.
- **Minor residual uncertainty** on whether `next_draft.md` has been informally adopted after the 2026-07-31 meeting. There is no later dated document to confirm or deny this. Until a new signed procedure supersedes `current.md`, the current procedure remains authoritative per the meeting record.
- **Low relevance uncertainty**: The `requirements.md` file (R3: "reconcile the procedure conflict") is satisfied by the meeting notes' explicit resolution. Other requirements (R1, R2, R4, R5) are addressed by the current procedure's steps but fall outside the scope of workflow authoritativeness.

## Conclusion

The authoritative workflow is **`procedures/current.md`**, confirmed by:
1. Its own title ("Current procedure — signed operational source of truth")
2. Explicit confirmation in `notes/meeting_notes.md` ("The signed current procedure remains the operational source of truth")
3. The non-authoritative status of all alternatives (previous is superseded; next_draft is unapproved)
