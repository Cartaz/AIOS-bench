"""
CSV reader with typed internal structures and strict validation.

Supports two CSV schemas: expenses and sales.  Parses, validates, and
returns lists of typed dataclass instances.
"""

from __future__ import annotations

import csv
import io
import os
from pathlib import Path
from typing import Dict, List, TextIO, Tuple

from .records import (
    EmptyDatasetError,
    ExpenseRecord,
    ExpenseRecord as _ExpenseRecord,
    InvalidDatasetError,
    RecordError,
    SalesRecord,
    _detect_schema,
)

# Public-facing type aliases
ParsedRecords = List[ExpenseRecord] | List[SalesRecord]


def parse_csv_file(filepath: str | Path) -> Tuple[str, ParsedRecords]:
    """Parse a CSV file and return (schema, records).

    Args:
        filepath: Path to a CSV file.

    Returns:
        A tuple of (schema_name, list_of_records).

    Raises:
        FileNotFoundError: If *filepath* does not exist.
        InvalidDatasetError: On structural problems (bad header, empty file).
        RecordError: On individual row validation failures.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")

    if path.stat().st_size == 0:
        raise EmptyDatasetError(f"CSV file is empty: {filepath}")

    with path.open("r", newline="", encoding="utf-8") as fh:
        return parse_csv_text(fh, filepath)


def parse_csv_text(fh: TextIO, source_label: str = "<stream>") -> Tuple[str, ParsedRecords]:
    """Parse CSV from a file-like object.

    Args:
        fh: Open file handle (read mode).
        source_label: Human-friendly label used in error messages.

    Returns:
        A tuple of (schema_name, list_of records).
    """
    text = fh.read()
    return parse_csv_string(text, source_label)


def parse_csv_string(text: str, source_label: str = "<string>") -> Tuple[str, ParsedRecords]:
    """Parse CSV from a plain string.

    Args:
        text: CSV content as a string.
        source_label: Human-friendly label used in error messages.

    Returns:
        A tuple of (schema_name, list_of_records).
    """
    if not text.strip():
        raise EmptyDatasetError(f"CSV content is empty: {source_label}")

    reader = csv.DictReader(io.StringIO(text))
    raw_header = reader.fieldnames
    if raw_header is None:
        raise InvalidDatasetError(f"No header found in {source_label}")

    normalised_header = [h.strip().lower() for h in raw_header]
    schema = _detect_schema(normalised_header)

    # Re-create DictReader with normalised header names
    rows_iter = csv.DictReader(io.StringIO(text), fieldnames=normalised_header)
    next(rows_iter)  # skip header

    records: ParsedRecords = []
    errors: List[Tuple[int, RecordError]] = []

    for i, row in enumerate(rows_iter, start=1):
        # Strip whitespace from all values
        cleaned = {k: (v.strip() if v else "") for k, v in row.items()}
        try:
            if schema == "expense":
                rec = ExpenseRecord.from_row(cleaned, row_index=i)
            else:
                rec = SalesRecord.from_row(cleaned, row_index=i)
            records.append(rec)  # type: ignore[arg-type]
        except RecordError as exc:
            errors.append((i, exc))

    if errors:
        # Report first error for determinism (fail-fast), but attach others
        first_row, first_exc = errors[0]
        extra = "; ".join(f"row {r}: {e.message}" for r, e in errors[1:])
        msg = first_exc.message
        if extra:
            msg += f" (and {len(errors) - 1} more errors)"
        raise RecordError(
            msg,
            row=first_row,
            column=getattr(first_exc, "column", None),
        )

    if not records:
        raise EmptyDatasetError(f"No data rows in {source_label}")

    return schema, records


def load_dataset(path: str | Path) -> Tuple[str, ParsedRecords]:
    """Convenience wrapper: detect schema and load records from a file.

    Walks parent directories to look for the CSV relative to the caller's
    module *or* accepts an absolute/relative path directly.
    """
    return parse_csv_file(path)
