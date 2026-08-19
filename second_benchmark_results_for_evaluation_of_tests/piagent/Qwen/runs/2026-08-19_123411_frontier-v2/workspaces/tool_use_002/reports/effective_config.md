# Effective Configuration Report

## Overview

This report resolves the configuration indirection described in `README.md` and determines the effective settings for this workspace by examining procedure files, data sources, and consumer code.

## Source of Configuration

- **README.md** — Lists workspace files but contains no direct configuration. It serves as an index pointing to `procedures/` for process definitions.
- **`procedures/current.md`** — **ACTIVE** procedure (effective config).
- **`procedures/previous.md`** — **OBSOLETE** procedure (superseded by `current.md`).

## Indirection Resolution

| Layer | File | Role |
|-------|------|------|
| Top-level index | `README.md` | Lists data files, procedure files, and the broken tool |
| Active procedure | `procedures/current.md` | Defines the processing pipeline (effective settings) |
| Previous procedure | `procedures/previous.md` | Old pipeline (ignored; superseded) |
| Data source | `data/sales.csv` | Input for the current procedure |
| Consumer code | `projects/broken_tool.py` | Utility function (buggy — see Verification section) |

## Effective Settings (from `procedures/current.md`)

### Processing Pipeline

1. **Input**: Monthly sales CSV (`data/sales.csv`)
2. **Validate**: Check header and numeric fields
3. **Compute**: Total revenue and total units
4. **Output**: Summary saved as `reports/monthly-sales.md`
5. **Review**: Manual review step before sharing

### Key Differences from Previous Procedure

| Setting | Previous (`procedures/previous.md`) | Current (`procedures/current.md`) |
|---------|-------------------------------------|-----------------------------------|
| Output file extension | `.txt` | `.md` |
| Validation step | ❌ None | ✅ Required (header + numeric fields) |
| Total units computed | ❌ Revenue only | ✅ Revenue **and** units |
| Review step | ❌ Sent without review | ✅ Required before sharing |

## Data Source Verification

### `data/sales.csv`
- **Columns**: `date`, `product`, `units`, `revenue`
- **Record count**: 6 rows (July 2026)
- **Computed totals**:
  - **Total Revenue**: 580
  - **Total Units**: 41
- **Products**: A (3 entries), B (2 entries), C (1 entry)

### `data/expenses.csv`
- **Columns**: `date`, `category`, `description`, `amount`
- **Record count**: 6 rows (July 2026)
- **Computed total**: 91.07
- **By category**: software=49.97, office=12.70, travel=28.40

### `notes/meeting_notes.md`
- **Meeting date**: 2026-07-31
- **Actions assigned**:
  - Marta: prepare July sales summary (directly relates to this task)
- **Decisions**: Keep cloud storage subscription; review recurring costs monthly

## Consumer Code Verification

### `projects/broken_tool.py` — BUG CONFIRMED

**Bug**: Type error when summing mixed types.

```python
def monthly_total(values):
    total = 0
    for value in values:
        total += value   # TypeError if value is a string
    return total

# Invocation passes a string:
print(monthly_total([10, 20, "30"]))
```

**Error**: `TypeError: unsupported operand type(s) for +=: 'int' and 'str'`

**Root cause**: The function assumes all values are numeric but receives a string `"30"`. It does not handle type coercion.

**Fix** (not applied per task constraints): Convert each value to `int` or `float` before adding:
```python
total += int(value)  # or float(value)
```

## Summary of Effective Configuration

| Setting | Value |
|---------|-------|
| **Active procedure** | `procedures/current.md` |
| **Input file** | `data/sales.csv` |
| **Output file** | `reports/monthly-sales.md` |
| **Validation** | Header + numeric fields must be validated |
| **Metrics** | Total revenue (580), Total units (41) |
| **Review** | Required before sharing |
| **Broken tool status** | `projects/broken_tool.py` fails with TypeError on non-numeric input |
