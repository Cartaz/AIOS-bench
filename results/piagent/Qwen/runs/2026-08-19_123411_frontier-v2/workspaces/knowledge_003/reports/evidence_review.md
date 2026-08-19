# Evidence Review — Workflow Authority Resolution

## 1. Source Inventory

| Source | File | Nature | Date |
|---|---|---|---|
| Current procedure | `procedures/current.md` | Operating procedure | Undated (revision state) |
| Previous procedure | `procedures/previous.md` | Operating procedure (superseded) | Undated |
| Meeting notes | `notes/meeting_notes.md` | Meeting decisions/notes | 2026-07-31 |

No other source files contain workflow instructions.

## 2. Claim–Evidence Matrix

| # | Claim | Current Procedure | Previous Procedure | Meeting Notes | Supported? |
|---|---|---|---|---|---|
| C1 | Export the monthly sales CSV as step 1. | ✅ Step 1 | ✅ Step 1 | ❌ Not mentioned | Partially (2/3) |
| C2 | Validate header and numeric fields. | ✅ Step 2 | ❌ Not mentioned | ❌ Not mentioned | Only current |
| C3 | Calculate total revenue and units. | ✅ Step 3 | ✅ Step 2 | ❌ Not mentioned | 2/3 |
| C4 | Save as `reports/monthly-sales.md`. | ✅ Step 4 | ❌ Says `.txt` | ❌ Not mentioned | Only current |
| C5 | Save as `reports/monthly-sales.txt`. | ❌ Says `.md` | ✅ Step 3 | ❌ Not mentioned | Only previous |
| C6 | Review result before sharing. | ✅ Step 5 | ❌ "without a separate review step" | ❌ Not mentioned | Only current |
| C7 | Send without a separate review step. | ❌ Requires review | ✅ Step 4 | ❌ Not mentioned | Only previous |

## 3. Contradictions

1. **Output format:** `.md` (current) vs `.txt` (previous)
2. **Review step:** Required (current) vs Explicitly absent (previous)
3. **Data validation:** Required (current) vs Not mentioned (previous)

Meeting notes are silent on all conflict areas.

## 4. Authority Criteria

| Criterion | Rationale | Weight |
|---|---|---|
| C1: Temporal recency | Most recently written/superseded document carries more weight | High |
| C2: Explicit supersession | "current" vs "previous" labelling signals deliberate state transition | High |
| C3: Context specificity | Documents matching the decision context | Medium |
| C4: Formality | Procedures outrank notes and data | Medium |
| C5: Meeting override | Notes only override if they explicitly address the topic | Low |

## 5. Ranking

1. **Current procedure** — High on recency, supersession, formality. **Authoritative.**
2. **Meeting notes** — Medium on recency, context; silent on conflict points. Consultable but non-authoritative.
3. **Previous procedure** — Superseded. Explicitly outdated. Non-authoritative.

## 6. Resolutions

- **Output:** `reports/monthly-sales.md` (current procedure)
- **Review:** Required (current procedure, Step 5)
- **Validation:** Required (current procedure, Step 2)

## 7. Recommendation

**Current procedure (`procedures/current.md`) is authoritative.**

**Uncertainty: Low.** The "current"/"previous" labelling is unambiguous. The meeting notes assign Luca to update the procedure, indirectly supporting the current procedure as the post-meeting state. The only caveat is the undocumented temporal ordering between procedure versions and the meeting date.
