from __future__ import annotations

import csv
import json
from pathlib import Path


def seed(root: str | Path) -> None:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "business").mkdir(exist_ok=True)
    (root / "business" / "reports").mkdir(exist_ok=True)
    (root / "project").mkdir(exist_ok=True)

    (root / "business" / "README.md").write_text(
        """# Demo business workspace\n\nUse the CSV files to create monthly reports. Do not modify source data.\n\nPreferred report format: HTML with a short executive summary, totals, and anomalies.\n""", encoding="utf-8"
    )
    sales = [
        ["date", "client", "amount", "status"],
        ["2026-06-03", "Atlas", "1200", "paid"],
        ["2026-06-08", "Boreal", "850", "paid"],
        ["2026-07-02", "Atlas", "1300", "paid"],
        ["2026-07-14", "Boreal", "900", "pending"],
        ["2026-07-29", "Cetus", "7200", "paid"],
        ["2026-08-03", "Atlas", "1250", "paid"],
        ["2026-08-09", "Boreal", "910", "paid"],
        ["2026-08-11", "Cetus", "680", "paid"],
    ]
    with (root / "business" / "sales.csv").open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(sales)

    expenses = [
        ["date", "category", "description", "amount"],
        ["2026-07-01", "software", "Editor", "18"],
        ["2026-07-04", "hosting", "Server", "42"],
        ["2026-07-12", "travel", "Train", "67"],
        ["2026-08-02", "software", "Editor", "18"],
        ["2026-08-05", "hosting", "Server", "42"],
        ["2026-08-10", "travel", "Train", "67"],
        ["2026-08-12", "equipment", "Monitor", "390"],
    ]
    with (root / "business" / "expenses.csv").open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(expenses)

    (root / "business" / "notes.md").write_text(
        """# Meeting notes\n\n- 2026-08-04: Monthly reports should flag unusually large transactions.\n- 2026-08-07: Reports must not overwrite source CSVs.\n- 2026-08-12: Keep generated artifacts under `reports/`.\n""", encoding="utf-8"
    )
    (root / "project" / "config.json").write_text(
        json.dumps({"name": "demo-tool", "language": "python", "format": "html", "version": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "project" / "broken.py").write_text(
        "def total(values):\n    return sum(values)\n\nprint(total([10, 20, '30']))\n", encoding="utf-8"
    )
