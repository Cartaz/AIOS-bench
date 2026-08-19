# Retained Workflow Preferences

## Current Preferences (as of 2026-07-31)

1. **Automation tool language: TypeScript** — Use TypeScript for new automation tools instead of Python.
2. **Keep tools simple** — Favor simplicity and maintainability in tool design.
3. **No unsolicited Git commits** — Never create a Git commit without explicit user approval.

## What Changed

| Previously Stated (memory_001) | Now Updated (memory_003) |
|---|---|
| Use **Python** for small automation tools | Use **TypeScript** for new automation tools |

The user has switched from Python to TypeScript as the preferred language for building new automation tools. All other preferences remain unchanged.

## Conflict Resolution

The durable preference for automation tool language was explicitly overridden by the user in this session. When preferences conflict, newer explicit user statements take precedence over older ones. The Python preference is superseded for *new* tools only; existing Python tools (e.g., `projects/broken_tool.py`) are left untouched as they are part of the workspace source data. The other two preferences — keep tools simple and no unsolicited Git commits — remain in full effect.
