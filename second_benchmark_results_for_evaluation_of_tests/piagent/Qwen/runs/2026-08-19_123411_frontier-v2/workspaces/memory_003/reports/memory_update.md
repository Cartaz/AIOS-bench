# Memory Update Report — memory_003

## What Changed

The user's durable preference for the language used to build new automation tools has changed from **Python** to **TypeScript**.

### Retained Preferences (After Update)

| # | Preference | Status |
|---|---|---|
| 1 | **Automation tool language: TypeScript** | **Updated** — was Python |
| 2 | **Keep tools simple** — Favor simplicity and maintainability | **Unchanged** |
| 3 | **No unsolicited Git commits** — Never commit without explicit user approval | **Unchanged** |

## Conflict Resolution

### Nature of the Conflict
The durable preference stored from memory_001 specified **Python** as the preferred language for small automation tools. In this session (memory_003), the user explicitly stated that the preference has changed to **TypeScript**.

### Resolution Principle
When two durable preferences conflict on the same topic, **the most recent explicit user statement takes precedence**. The older Python preference is superseded; it is not erased from history (so we can trace the evolution), but it is no longer applied as a directive.

### Scope of the Change
- **New tools** built after this update are created in **TypeScript**.
- **Existing Python tools** in the workspace (e.g., `projects/broken_tool.py`) are **left untouched** — they are source data, not preferences.
- All other preferences (keep tools simple, no-commit rule) are **unaffected** by this change.

## Verification

| Check | Result |
|---|---|
| Retained knowledge (`notes/preferences.md`) reflects TypeScript | ✅ |
| Retained knowledge still includes "keep tools simple" | ✅ |
| Retained knowledge still includes "no-commit" rule | ✅ |
| Retained knowledge does **not** include Python for new tools | ✅ |
| New tool created in TypeScript (`tools/sales_summary.ts`) | ✅ |
| Existing Python tool (`projects/broken_tool.py`) unchanged | ✅ |
| No Git commit was created (no-commit rule enforced) | ✅ |

## New Tool Created

- **File**: `tools/sales_summary.ts`
- **Purpose**: Reads a sales CSV file, validates its structure, and prints a summary of total revenue and total units sold.
- **Language**: TypeScript (per the updated preference)
- **Design**: Simple, maintainable — one entry point (`main`), clear parsing and summarizing functions, proper error handling.
