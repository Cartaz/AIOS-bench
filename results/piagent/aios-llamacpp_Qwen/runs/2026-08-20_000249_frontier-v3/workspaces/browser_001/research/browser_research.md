# Python 3.14 sqlite3 Transaction Control — Browser Research Report

**Date of Research:** 2026-08-20
**Python Version Evaluated:** 3.14.7
**Task:** Research Python 3.14 sqlite3 transaction control, verify default isolation level, reconcile version-specific guidance.

---

## Sources

### Source 1 — Python 3.14 Official Documentation (sqlite3 module)
- **URL:** https://docs.python.org/3.14/library/sqlite3.html
- **Section:** "Transaction control" → "Transaction control via the autocommit attribute" and "Transaction control via the isolation_level attribute"
- **Access Date:** 2026-08-20
- **Key Content:** Complete specification of the two transaction control mechanisms (`autocommit` attribute and `isolation_level` attribute), their interaction, and the `LEGACY_TRANSACTION_CONTROL` sentinel.

### Source 2 — Python 3.12 Release Notes (What's New in Python 3.12)
- **URL:** https://docs.python.org/3.14/whatsnew/3.12.html
- **Section:** "sqlite3" changes
- **Access Date:** 2026-08-20
- **Key Content:** Introduces `sqlite3.Connection.autocommit` attribute and `autocommit` parameter to `sqlite3.connect()`, implementing PEP 249-compliant transaction handling.

### Source 3 — SQLite Official Documentation (Transactions)
- **URL:** https://www.sqlite.org/lang_transaction.html
- **Section:** "DEFERRED, IMMEDIATE, and EXCLUSIVE transactions"
- **Access Date:** 2026-08-20
- **Key Content:** Defines the three SQLite transaction types (DEFERRED, IMMEDIATE, EXCLUSIVE) at the C library level. Confirms DEFERRED is the default SQLite transaction behavior.

### Source 4 — PEP 249 — Python Database API Specification v2.0
- **URL:** https://peps.python.org/pep-0249/
- **Section:** "Connection.autocommit"
- **Access Date:** 2026-08-20
- **Key Content:** Defines the `autocommit` attribute interface for DB-API 2.0 compliance: `True` for autocommit (non-transactional) mode, `False` for manual commit (transactional) mode.

### Source 5 — Python 3.14 Release Notes (What's New in Python 3.14)
- **URL:** https://docs.python.org/3.14/whatsnew/3.14.html
- **Section:** "sqlite3" changes
- **Access Date:** 2026-08-20
- **Key Content:** Minor sqlite3 changes in 3.14 (no new transaction control changes from 3.12); the autocommit mechanism from 3.12 is fully stable in 3.14.

---

## Verified Default Isolation Level

**The verified default isolation level for Python 3.14 sqlite3 is `DEFERRED`.**

Evidence:
1. The `sqlite3.connect()` function signature in the Python 3.14 documentation declares `isolation_level='DEFERRED'` as the default parameter.
2. When `autocommit` is at its default value of `sqlite3.LEGACY_TRANSACTION_CONTROL` (-1), the `isolation_level` attribute is read as an empty string `''`, which the documentation explicitly states is "an alias for 'DEFERRED'".
3. Programmatically verified: a connection created with default settings enters a transaction (`in_transaction == True`) after the first write statement, consistent with DEFERRED semantics.
4. The underlying SQLite C library's own default transaction type is DEFERRED.

---

## Two-Mode Transaction Control Architecture (Python 3.12+)

Starting in Python 3.12, sqlite3 offers **two** transaction control mechanisms:

### 1. PEP 249-Compliant Mode (Recommended): `autocommit` attribute

| `autocommit` value | Behavior |
|---|---|
| `False` | PEP 249-compliant. A transaction is **always open**. Uses `BEGIN DEFERRED` when opening. `commit()` and `rollback()` close/open transactions. **Recommended.** |
| `True` | SQLite autocommit mode. Every statement is its own transaction. `commit()` and `rollback()` have no effect. |
| `LEGACY_TRANSACTION_CONTROL` (-1) | Delegates control to the legacy `isolation_level` attribute. **This is the default.** |

**Default:** `autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL` (-1)

### 2. Legacy Mode: `isolation_level` attribute (only active when `autocommit == LEGACY_TRANSACTION_CONTROL`)

| `isolation_level` value | BEGIN statement issued | Transaction behavior |
|---|---|---|
| `"DEFERRED"` (or `""`) | `BEGIN DEFERRED` | Transaction starts on first read/write. **Default.** |
| `"IMMEDIATE"` | `BEGIN IMMEDIATE` | Write lock acquired immediately on BEGIN. |
| `"EXCLUSIVE"` | `BEGIN EXCLUSIVE` | Write lock acquired immediately; prevents other readers. |
| `None` | No BEGIN issued | No implicit transactions. SQLite in autocommit mode. Manual `BEGIN`/`COMMIT`/`ROLLBACK` via SQL. |

---

## Version-Specific Guidance & Reconciliation

### Python 3.11 and earlier
- Only `isolation_level` attribute existed.
- Default: `isolation_level='DEFERRED'`.
- Implicit transaction opening before DML statements.
- No `autocommit` attribute.

### Python 3.12
- **Breaking change:** New `autocommit` attribute and parameter introduced.
- **Backward compatibility:** Default `autocommit=LEGACY_TRANSACTION_CONTROL` preserves pre-3.12 behavior via `isolation_level`.
- `isolation_level` still works but only when `autocommit` is `LEGACY_TRANSACTION_CONTROL`.
- Documentation recommends switching to `autocommit=False` for PEP 249 compliance.

### Python 3.14 (current)
- Both mechanisms fully stable.
- `autocommit=LEGACY_TRANSACTION_CONTROL` remains the default for backward compatibility.
- The recommended path is `autocommit=False` (PEP 249-compliant manual commit mode).
- No changes to transaction control from Python 3.12 to 3.14.

### Reconciliation
The apparent discrepancy between the documented default of `isolation_level='DEFERRED'` in the `connect()` signature and the actual runtime value of `conn.isolation_level == ''` is resolved: the empty string is an alias for `"DEFERRED"`. Both the documentation and runtime behavior consistently indicate that **DEFERRED** is the effective default isolation level.

---

## Key API Elements

| Symbol | Type | Description |
|---|---|---|
| `sqlite3.LEGACY_TRANSACTION_CONTROL` | Constant (-1) | Legacy (pre-3.12) transaction control mode |
| `Connection.autocommit` | Attribute | PEP 249 transaction control (`True`, `False`, or `LEGACY_TRANSACTION_CONTROL`) |
| `Connection.isolation_level` | Attribute | Legacy transaction control (`"DEFERRED"`, `"IMMEDIATE"`, `"EXCLUSIVE"`, or `None`) |
| `Connection.in_transaction` | Attribute | Low-level SQLite autocommit mode status (`bool`) |
| `sqlite3.connect(..., autocommit=...)` | Parameter | Set initial autocommit mode at connection |
| `sqlite3.connect(..., isolation_level=...)` | Parameter | Set initial legacy isolation level at connection |
| `Connection.commit()` | Method | Commit pending transaction |
| `Connection.rollback()` | Method | Roll back pending transaction |

---

## Summary

The **verified default isolation level** for Python 3.14 sqlite3 is **DEFERRED** (represented as empty string `''` in the `isolation_level` attribute when `autocommit` is at its default of `LEGACY_TRANSACTION_CONTROL`). The recommended modern approach is to use `autocommit=False` for PEP 249-compliant manual transaction control, which uses `BEGIN DEFERRED` by default.
