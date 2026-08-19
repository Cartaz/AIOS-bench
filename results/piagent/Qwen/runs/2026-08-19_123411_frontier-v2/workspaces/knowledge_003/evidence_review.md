# Evidence Review — Workflow Authority Resolution

## 1. Source Inventory

| Source | File | Nature | Date |
|---|---|---|---|
| Current procedure | `procedures/current.md` | Operating procedure | Undated (revision state) |
| Previous procedure | `procedures/previous.md` | Operating procedure (superseded) | Undated |
| Meeting notes | `notes/meeting_notes.md` | Meeting decisions/notes | 2026-07-31 |

**No other source files contain workflow instructions.** The CSV files (`data/expenses.csv`, `data/sales.csv`) contain raw data only. The Python file (`projects/broken_tool.py`) is a debugging fixture with no procedural content.

---

## 2. Claim–Evidence Matrix

Each claim below is tested against all three sources.

| # | Claim | Current Procedure | Previous Procedure | Meeting Notes | Supported? |
|---|---|---|---|---|---|
| C1 | Export the monthly sales CSV as step 1. | ✅ Step 1 | ✅ Step 1 | ❌ Not mentioned | Partially (two of three) |
| C2 | Validate header and numeric fields before calculations. | ✅ Step 2 | ❌ Not mentioned | ❌ Not mentioned | Only current |
| C3 | Calculate total revenue and units. | ✅ Step 3 ("total revenue and units") | ✅ Step 2 ("total revenue") | ❌ Not mentioned | Two of three (C2 differs) |
| C4 | Save the summary as `reports/monthly-sales.md` (Markdown). | ✅ Step 4 | ❌ Says `.txt` | ❌ Not mentioned | Only current |
| C5 | Save the summary as `reports/monthly-sales.txt` (text). | ❌ Says `.md` | ✅ Step 3 | ❌ Not mentioned | Only previous |
| C6 | Review the result before sharing it. | ✅ Step 5 | ❌ Explicitly *omitted* — Step 4 says "Send the summary without a separate review step." | ❌ Not mentioned | Only current |
| C7 | Send the summary without a separate review step. | ❌ Requires review | ✅ Step 4 | ❌ Not mentioned | Only previous |

---

## 3. Identified Contradictions

| # | Conflict Area | Current Procedure | Previous Procedure | Meeting Notes |
|---|---|---|---|---|
| Contradiction 1 | **Output file extension** | `.md` (Markdown) | `.txt` (plain text) | Silent |
| Contradiction 2 | **Review step** | Required (Step 5) | Explicitly absent — "without a separate review step" | Silent |
| Contradiction 3 | **Data validation** | Required (header + numeric fields, Step 2) | Not mentioned (implied absent) | Silent |

The meeting notes are **silent** on all three conflict areas. They do not explicitly endorse either procedure.

---

## 4. Authority Criteria (Explicit)

To rank the authority of these three sources when they conflict, I apply the following criteria:

| Criterion | Rationale | Weight |
|---|---|---|
| **C1: Temporal recency** | The most recently written or superseded document should carry more weight, as it reflects the latest organisational intent. | High |
| **C2: Explicit supersession** | If a document is labelled "previous" vs. "current", the labelling itself signals a deliberate state transition. | High |
| **C3: Specificity to the decision context** | Documents authored or referenced in the relevant meeting's decisions carry more weight than generic procedural files. | Medium |
| **C4: Formality / procedural status** | Documents that are labelled as procedures (as opposed to notes or data) are normative instructions and outrank non-normative sources. | Medium |
| **C5: Meeting notes as a corrective mechanism** | Meeting notes can override or amend procedures, but only if they explicitly address the topic. Silent silence = no override. | Low |

---

## 5. Ranking with Applied Criteria

| Rank | Source | C1 (Recency) | C2 (Supersession) | C3 (Context) | C4 (Formality) | C5 (Meeting override) | Summary |
|---|---|---|---|---|---|---|---|
| 1 | **Current procedure** (`procedures/current.md`) | High — labelled "current", implying it supersedes | High — explicitly the active version | Low — generic procedure | High — formal procedure | N/A | **Authoritative.** Both recency and supersession labels align. |
| 2 | **Meeting notes** (`notes/meeting_notes.md`) | Medium — dated 2026-07-31 | Low — not a procedure | Medium — discusses July operations, assigns Luca to update procedures | Low — meeting notes, not a procedure | Low — silent on all conflict points; no override | **Consultable but non-authoritative** on the conflicted points. It assigns Luca to "update the current operating procedure," which *supports* the existence of the current procedure as the post-meeting update. |
| 3 | **Previous procedure** (`procedures/previous.md`) | Low — superseded | Low — labelled "previous" | Low | High — formal procedure | N/A | **Non-authoritative.** Retains procedural formality but is explicitly outdated. |

**Key observation from the meeting notes:**
> "Luca: update the current operating procedure after the meeting."

This action item, set on 2026-07-31, assigns someone to update the procedure. The existence of a file explicitly labelled **current.md** (vs. **previous.md**) strongly suggests that this update action was completed and the resulting document is `procedures/current.md`. The meeting notes, therefore, *indirectly* validate the current procedure as the post-meeting state — even though they are silent on the specific conflict details.

---

## 6. Resolution of Each Contradiction

### Contradiction 1 — Output file extension (`.md` vs `.txt`)
- **Resolution:** Current procedure (`monthly-sales.md`) is authoritative.
- **Rationale:** Temporal recency (C1) and explicit supersession (C2) both favour the current procedure. The previous procedure's `.txt` extension is superseded.

### Contradiction 2 — Review step (required vs. absent)
- **Resolution:** Review is required per the current procedure (Step 5).
- **Rationale:** The previous procedure's instruction to "send without a separate review" is explicitly negated by the current procedure's Step 5. Temporal recency (C1) and supersession (C2) both favour the current procedure. The meeting notes' silence means they do not override.

### Contradiction 3 — Data validation (required vs. not mentioned)
- **Resolution:** Header and numeric field validation is required per the current procedure (Step 2).
- **Rationale:** The current procedure adds a new step (Step 2) that was absent from the previous procedure. This is a net addition of a quality-control step, consistent with the more rigorous current procedure. No meeting note contradicts this.

---

## 7. Overall Recommendation

**The current procedure (`procedures/current.md`) is the authoritative workflow when conflicts arise between the three sources.**

### Uncertainty Assessment: **Low**

- **Reasons for low uncertainty:**
  - The labelling ("current" vs. "previous") provides an explicit, unambiguous supersession signal.
  - The meeting notes assign an action item to update the procedure, which aligns with the existence of the current procedure as the post-meeting artifact.
  - The meeting notes are silent on the conflict areas, meaning no higher-authority source (the meeting decisions) contradicts the current procedure.

- **Limitations / Caveats:**
  - The meeting notes do not *explicitly* endorse the current procedure's specific changes (extension, review step, validation). There is a small residual uncertainty that the current procedure was modified independently of the meeting or without team consensus.
  - The temporal relationship between the procedure versions and the meeting date (2026-07-31) is not explicitly documented. We infer that the current procedure is the post-meeting update, but this is not stated in any file.

---

## 8. Conclusion

When current and previous procedures conflict with meeting notes (or with each other):

1. **Meeting notes** override procedures **only if** they explicitly address the conflicting topic. Here, the notes are silent, so they do not override.
2. **The current procedure** overrides the previous procedure because it is explicitly the active, superseding version.
3. **The previous procedure** is non-authoritative on all conflict points.

**Authoritative source: `procedures/current.md`**
