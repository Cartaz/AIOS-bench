# CSV Reporting Utility

A robust, local reporting utility that reads structured CSV data, validates it with typed internal structures, and produces deterministic Markdown reports.

## Project Structure

```
reporting/
├── __init__.py      # Package init & CLI entry-point
├── main.py          # CLI entry-point (python -m reporting.main)
├── records.py       # Typed dataclasses + strict validation
├── loader.py        # CSV parsing & schema detection
├── report.py        # Markdown report generation
└── tests.py         # Full test suite (42 tests)
```

## Supported Schemas

### Expense CSV
| Column       | Type   | Constraints                    |
|------------- |--------|--------------------------------|
| `date`       | date   | YYYY-MM-DD                     |
| `category`   | enum   | software, office, travel, ...  |
| `description`| string | non-empty                      |
| `amount`     | number | non-negative decimal           |

### Sales CSV
| Column     | Type   | Constraints               |
|----------- |--------|---------------------------|
| `date`     | date   | YYYY-MM-DD                |
| `product`  | string | non-empty                 |
| `units`    | int    | non-negative integer      |
| `revenue`  | number | non-negative decimal      |

## Usage

### CLI

```bash
# Generate expense report
python -m reporting.main data/expenses.csv reports/expense-report.md

# Generate sales report
python -m reporting.main data/sales.csv reports/sales-report.md

# Default output path (reports/report.md)
python -m reporting.main data/expenses.csv
```

### Programmatic API

```python
from reporting.loader import parse_csv_file
from reporting.report import generate_report, save_report

# Load and validate
schema, records = parse_csv_file("data/expenses.csv")
# schema == "expense", records is list[ExpenseRecord]

# Generate report
content = generate_report(schema, records)

# Save
save_report(content, "reports/my-report.md")
```

### Error Handling

```python
from reporting.loader import parse_csv_file
from reporting.records import (
    RecordError,       # Bad row data (invalid date, non-numeric amount, …)
    EmptyDatasetError, # No data rows (empty file or header-only)
    InvalidDatasetError, # Unrecognised schema
)

try:
    schema, records = parse_csv_file("data/bad.csv")
except FileNotFoundError:
    print("File not found")
except EmptyDatasetError:
    print("No data to report")
except RecordError as exc:
    print(f"Row {exc.row} error: {exc.message}")
except InvalidDatasetError:
    print("Unrecognised CSV format")
```

## Running Tests

```bash
cd /path/to/workspace
python -m reporting.tests -v
```

42 tests cover:
- Schema detection (valid, case-insensitive, unknown)
- ExpenseRecord validation (date, category, description, amount)
- SalesRecord validation (date, product, units, revenue)
- Malformed CSV handling (bad dates, non-numeric values, empty fields, multiple errors)
- Empty dataset handling (empty file, header-only)
- Deterministic output (sorted categories, sorted dates, idempotent reports)
- File-based loader (missing file, empty file, real data files)
- CLI exit codes (success, missing file, malformed data, empty data)

## Determinism

All reports are deterministic:
- Categories and products are sorted alphabetically
- Table entries are sorted by date
- Running the same input twice produces byte-identical output (aside from the timestamp)
