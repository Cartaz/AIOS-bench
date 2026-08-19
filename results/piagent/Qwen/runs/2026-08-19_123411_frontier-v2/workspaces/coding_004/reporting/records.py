"""
Typed internal structures for the CSV reporting utility.

Defines dataclasses with strict validation for the two supported CSV schemas:
- ExpenseReport (date, category, description, amount)
- SalesReport   (date, product, units, revenue)
"""

from __future__ import annotations

from dataclasses import dataclass, fields, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Type, TypeVar
from decimal import Decimal, InvalidOperation
from enum import Enum


class RecordError(Exception):
    """Raised when a record fails validation."""

    def __init__(self, message: str, row: Optional[int] = None, column: Optional[str] = None):
        self.message = message
        self.row = row
        self.column = column
        parts = []
        if row is not None:
            parts.append(f"row {row}")
        if column is not None:
            parts.append(f"column '{column}'")
        location = f" at {', '.join(parts)}" if parts else ""
        super().__init__(f"{message}{location}")


class InvalidDatasetError(Exception):
    """Raised when the entire dataset fails structural validation."""

    def __init__(self, message: str, detail: Optional[str] = None):
        self.message = message
        self.detail = detail
        super().__init__(f"{message}" + (f": {detail}" if detail else ""))


class EmptyDatasetError(InvalidDatasetError):
    """Raised when a dataset contains no data rows."""
    pass


class Category(str, Enum):
    SOFTWARE = "software"
    OFFICE = "office"
    TRAVEL = "travel"
    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls, value: str) -> Optional["Category"]:
        # Normalise and try exact match
        normalised = value.strip().lower()
        for member in cls:
            if member.value == normalised:
                return member
        # Return UNKNOWN for unrecognised categories instead of failing
        return cls.UNKNOWN


@dataclass(frozen=True)
class ExpenseRecord:
    """A single validated expense line item."""
    date: date
    category: Category
    description: str
    amount: Decimal

    @classmethod
    def from_row(cls, row: Dict[str, str], row_index: int) -> "ExpenseRecord":
        """Parse and validate a single CSV row dict."""
        required = {"date", "category", "description", "amount"}
        missing = required - set(row.keys())
        if missing:
            raise RecordError(
                f"Missing required columns: {sorted(missing)}",
                row=row_index,
            )

        # --- date ---
        try:
            parsed_date = datetime.strptime(row["date"].strip(), "%Y-%m-%d").date()
        except (ValueError, AttributeError) as exc:
            raise RecordError(
                f"Invalid date format: {row['date']!r} (expected YYYY-MM-DD)",
                row=row_index,
                column="date",
            ) from exc

        # --- category ---
        raw_cat = row["category"].strip()
        try:
            category = Category(raw_cat)
        except Exception:
            category = Category.UNKNOWN
        if not raw_cat:
            raise RecordError("Category must not be empty", row=row_index, column="category")

        # --- description ---
        desc = row["description"].strip()
        if not desc:
            raise RecordError("Description must not be empty", row=row_index, column="description")

        # --- amount ---
        try:
            amount = Decimal(row["amount"].strip())
        except (InvalidOperation, AttributeError, ValueError) as exc:
            raise RecordError(
                f"Invalid numeric amount: {row['amount']!r}",
                row=row_index,
                column="amount",
            ) from exc
        if amount < 0:
            raise RecordError(
                f"Amount must be non-negative, got {amount}",
                row=row_index,
                column="amount",
            )

        return cls(date=parsed_date, category=category, description=desc, amount=amount)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "category": self.category.value,
            "description": self.description,
            "amount": str(self.amount),
        }


@dataclass(frozen=True)
class SalesRecord:
    """A single validated sales line item."""
    date: date
    product: str
    units: int
    revenue: Decimal

    @classmethod
    def from_row(cls, row: Dict[str, str], row_index: int) -> "SalesRecord":
        """Parse and validate a single CSV row dict."""
        required = {"date", "product", "units", "revenue"}
        missing = required - set(row.keys())
        if missing:
            raise RecordError(
                f"Missing required columns: {sorted(missing)}",
                row=row_index,
            )

        # --- date ---
        try:
            parsed_date = datetime.strptime(row["date"].strip(), "%Y-%m-%d").date()
        except (ValueError, AttributeError) as exc:
            raise RecordError(
                f"Invalid date format: {row['date']!r} (expected YYYY-MM-DD)",
                row=row_index,
                column="date",
            ) from exc

        # --- product ---
        product = row["product"].strip()
        if not product:
            raise RecordError("Product must not be empty", row=row_index, column="product")

        # --- units ---
        try:
            units = int(row["units"].strip())
        except (ValueError, AttributeError) as exc:
            raise RecordError(
                f"Invalid integer units: {row['units']!r}",
                row=row_index,
                column="units",
            ) from exc
        if units < 0:
            raise RecordError(
                f"Units must be non-negative, got {units}",
                row=row_index,
                column="units",
            )

        # --- revenue ---
        try:
            revenue = Decimal(row["revenue"].strip())
        except (InvalidOperation, AttributeError, ValueError) as exc:
            raise RecordError(
                f"Invalid numeric revenue: {row['revenue']!r}",
                row=row_index,
                column="revenue",
            ) from exc
        if revenue < 0:
            raise RecordError(
                f"Revenue must be non-negative, got {revenue}",
                row=row_index,
                column="revenue",
            )

        return cls(date=parsed_date, product=product, units=units, revenue=revenue)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "product": self.product,
            "units": self.units,
            "revenue": str(self.revenue),
        }


# ---------------------------------------------------------------------------
# Generic helper
# ---------------------------------------------------------------------------

T = TypeVar("T", ExpenseRecord, SalesRecord)


def _detect_schema(header: List[str]) -> str:
    """Return 'expense' or 'sales' based on the CSV header.

    Raises InvalidDatasetError if the header matches neither schema.
    """
    normalised = {h.strip().lower() for h in header}
    expense_cols = {"date", "category", "description", "amount"}
    sales_cols = {"date", "product", "units", "revenue"}
    if normalised == expense_cols:
        return "expense"
    if normalised == sales_cols:
        return "sales"
    raise InvalidDatasetError(
        "Unrecognised CSV schema",
        detail=f"Expected {{date, category, description, amount}} or {{date, product, units, revenue}}, got {header}",
    )
