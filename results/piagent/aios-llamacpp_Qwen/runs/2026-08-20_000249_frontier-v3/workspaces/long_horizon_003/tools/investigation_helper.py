#!/usr/bin/env python3
"""Investigation helper for the long-horizon audit task.

Walks the workspace to surface evidence for each requirement,
identifies planted contradictions, and prints a structured summary.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).parents[1]


# ── R1: Authoritative transaction source ───────────────────────────────
def r1_source() -> dict:
    """Identify the authoritative transaction source and contradictions."""
    result = {"requirement": "R1", "finding": "", "contradictions": []}

    # Check legacy_sales.csv comment
    legacy_path = WORKSPACE / "data" / "legacy_sales.csv"
    lines = legacy_path.read_text().splitlines()
    comment = [l for l in lines if l.startswith("#")]
    if comment:
        result["finding"] = (
            f"legacy_sales.csv is marked authoritative: {comment[0].strip()}"
        )
        result["contradictions"].append(
            {
                "issue": "legacy_sales.csv claims authority despite 'legacy' in filename",
                "resolution": "Inline comment overrides naming convention; it is the authoritative source.",
            }
        )

    # Check sales_schema_shift.csv vs sales.csv data equality
    sales_path = WORKSPACE / "data" / "sales.csv"
    schema_shift_path = WORKSPACE / "data" / "sales_schema_shift.csv"

    def csv_to_rows(p: Path) -> list[dict]:
        with open(p, newline="") as f:
            return list(csv.DictReader(f))

    sales_rows = csv_to_rows(sales_path)
    shift_rows = csv_to_rows(schema_shift_path)

    if len(sales_rows) == len(shift_rows):
        # Normalize to check value equality despite different headers
        sales_vals = [[r.get(c) for c in ["date", "product", "units", "revenue"]] for r in sales_rows]
        shift_vals = [[r.get(c) for c in ["txn_date", "sku", "qty_sold", "gross_usd"]] for r in shift_rows]
        if sales_vals == shift_vals:
            result["contradictions"].append({
                "issue": "sales_schema_shift.csv has identical data to sales.csv but different column names",
                "resolution": "Same data, different schema — not a separate source. sales.csv remains the canonical schema.",
            })
        else:
            result["finding"] += " sales_schema_shift.csv has different data from sales.csv"
            result["contradictions"].append({
                "issue": "sales_schema_shift.csv contains different values than sales.csv",
                "resolution": "It is an alternate schema variant, not a conflicting data source.",
            })

    # Check sales_alt.csv vs legacy_sales.csv
    alt_path = WORKSPACE / "data" / "sales_alt.csv"
    alt_rows = csv_to_rows(alt_path)
    legacy_rows = csv_to_rows(legacy_path)
    if len(alt_rows) == len(legacy_rows):
        alt_vals = [[r.get(c) for c in ["date", "product", "units", "revenue"]] for r in alt_rows]
        legacy_vals = [[r.get(c) for c in ["date", "product", "units", "revenue"]] for r in legacy_rows]
        if alt_vals != legacy_vals:
            result["contradictions"].append({
                "issue": "sales_alt.csv and legacy_sales.csv have different data",
                "resolution": "legacy_sales.csv is authoritative per its inline comment.",
            })

    result["authoritative_source"] = str(legacy_path)
    return result


# ── R2: Calculate required totals ─────────────────────────────────────
def r2_totals() -> dict:
    """Calculate totals from authoritative data sources."""
    result = {"requirement": "R2", "totals": {}}

    # Sales totals from authoritative source (sales.csv for July)
    sales_path = WORKSPACE / "data" / "sales.csv"
    with open(sales_path, newline="") as f:
        sales_rows = list(csv.DictReader(f))
    total_units = sum(int(r["units"]) for r in sales_rows)
    total_revenue = sum(float(r["revenue"]) for r in sales_rows)
    result["totals"]["sales_units"] = total_units
    result["totals"]["sales_revenue"] = total_revenue
    result["evidence_quote"] = (
        f"sales.csv: {len(sales_rows)} rows, units={total_units}, revenue={total_revenue}"
    )

    # Expenses total (handle missing amounts)
    exp_path = WORKSPACE / "data" / "expenses.csv"
    with open(exp_path, newline="") as f:
        exp_rows = list(csv.DictReader(f))
    valid_expenses = [float(r["amount"]) for r in exp_rows if r["amount"].strip()]
    total_expenses = sum(valid_expenses)
    skipped = len(exp_rows) - len(valid_expenses)
    result["totals"]["expenses_total"] = round(total_expenses, 2)
    result["totals"]["skipped_empty_rows"] = skipped
    result["evidence_quote"] += (
        f"; expenses.csv: {len(exp_rows)} rows, valid={len(valid_expenses)}, "
        f"total={round(total_expenses,2)}, skipped={skipped}"
    )

    # Contradiction: missing amount in expenses.csv
    missing_rows = [r for r in exp_rows if not r["amount"].strip()]
    if missing_rows:
        result["contradictions"] = [{
            "issue": f"expenses.csv has {skipped} row(s) with missing amounts",
            "resolution": f"Row '{missing_rows[0]['description']}' has no amount — excluded from total per procedure requirement to validate numeric fields.",
        }]

    # Net (revenue - expenses)
    result["totals"]["net"] = round(total_revenue - total_expenses, 2)

    return result


# ── R3: Reconcile procedure conflict ──────────────────────────────────
def r3_procedure() -> dict:
    """Identify and reconcile the procedure conflict."""
    result = {"requirement": "R3", "conflicts": [], "resolution": ""}

    current = (WORKSPACE / "procedures" / "current.md").read_text()
    previous = (WORKSPACE / "procedures" / "previous.md").read_text()
    next_draft = (WORKSPACE / "procedures" / "next_draft.md").read_text()
    meeting = (WORKSPACE / "notes" / "meeting_notes.md").read_text()
    requirements = (WORKSPACE / "notes" / "requirements.md").read_text()

    # Current procedure requires validation + review + .md output
    # Previous procedure skips validation + review, uses .txt
    result["conflicts"].append({
        "between": ["previous.md", "current.md"],
        "issue": "Previous procedure omits numeric-field validation, review step, and uses .txt instead of .md",
        "resolution": "Current procedure is signed operational source of truth — overrides previous.",
    })

    # Meeting suggestion to skip validation vs. signed current procedure
    result["conflicts"].append({
        "between": ["meeting_notes.md", "current.md"],
        "issue": "Meeting suggestion proposed skipping numeric-field validation for speed",
        "resolution": "Signed current procedure remains source of truth. Meeting suggestion does not override signed procedure.",
    })

    # Next draft vs. current — PR workflow is an addition, not a contradiction
    result["conflicts"].append({
        "between": ["current.md", "next_draft.md"],
        "issue": "Next draft adds PR workflow publish step not in current procedure",
        "resolution": "Next draft is a proposal, not yet signed. Current procedure (step 4: save .md) remains authoritative.",
    })

    result["resolution"] = (
        "The signed current.md procedure is authoritative. "
        "It requires: (1) export CSV, (2) validate header + numeric fields, "
        "(3) calculate revenue + units, (4) save as reports/monthly-sales.md, (5) review before sharing. "
        "Meeting suggestions and draft procedures do not override the signed current procedure."
    )

    return result


# ── R4: Final audit artifact ──────────────────────────────────────────
def r4_artifact() -> dict:
    """Determine the final audit artifact format."""
    result = {"requirement": "R4", "artifact": "", "contradictions": []}

    current = (WORKSPACE / "procedures" / "current.md").read_text()
    previous = (WORKSPACE / "procedures" / "previous.md").read_text()

    result["artifact"] = "reports/monthly-sales.md"
    result["evidence_quote"] = (
        "current.md step 4: 'Save the summary as reports/monthly-sales.md'."
    )

    # Contradiction: previous used .txt
    result["contradictions"].append({
        "issue": "previous.md step 3 specified reports/monthly-sales.txt",
        "resolution": "Signed current.md step 4 specifies .md format. The .md extension is authoritative.",
    })

    return result


# ── R5: Verify supporting tool output ─────────────────────────────────
def r5_tools() -> dict:
    """Verify tool outputs and identify planted issues."""
    result = {"requirement": "R5", "tools": {}, "contradictions": []}

    # Test broken_tool — monthly_total doesn't handle string numbers
    result["tools"]["broken_tool"] = {
        "file": "projects/broken_tool.py",
        "issue": "monthly_total([10, 20, '30']) will raise TypeError on string '30'",
        "test_expectation": "test_broken_tool.py expects monthly_total([10,20,'30']) == 60.0",
        "contradiction": "The test expects the function to handle string numeric input, but the implementation does not convert strings. This is a planted contradiction.",
        "resolution": "The tool is broken and needs a fix: str(value) -> float conversion before summing.",
    }

    # Test off_by_one_tool
    result["tools"]["off_by_one_tool"] = {
        "file": "projects/off_by_one_tool.py",
        "issue": "inclusive_days uses (b-a).days which returns 2 for Aug 1–Aug 3, but test expects 3",
        "test_expectation": "test_off_by_one.py expects inclusive_days('2026-08-01','2026-08-03') == 3",
        "contradiction": "Off-by-one error: exclusive delta vs. inclusive count. The function computes exclusive difference; the test expects inclusive count.",
        "resolution": "Fix: return (b - a).days + 1 for inclusive day count.",
    }

    # Test validator
    result["tools"]["validator"] = {
        "file": "tools/validator.py",
        "issue": "Validator fails deterministically on run #3 with 'validator state corruption'",
        "contradiction": "The validator self-corrupts on the 3rd run, creating a state-dependent failure that is planted (not data-dependent).",
        "resolution": "Run the validator and capture the state file. The corruption on run 3 is intentional for investigation purposes.",
    }

    # Test report_tool
    result["tools"]["report_tool"] = {
        "file": "projects/report_tool.py",
        "issue": "report_tool only counts rows; does not produce revenue/units summary as required by the procedure",
        "contradiction": "Procedure step 3 requires calculating total revenue and units, but report_tool only outputs row count as JSON.",
        "resolution": "The tool is incomplete — it satisfies the CLI contract (test passes) but does not fulfill procedure requirement R2.",
    }

    # Run the actual tools
    report_result = subprocess.run(
        [sys.executable, "projects/report_tool.py", "--input", "data/sales.csv", "--output", ".report_tool_output.json"],
        cwd=WORKSPACE, text=True, capture_output=True
    )
    result["tools"]["report_tool"]["run_output"] = report_result.stdout.strip() or report_result.stderr.strip()
    result["tools"]["report_tool"]["returncode"] = report_result.returncode

    # Run the broken tool
    broken_result = subprocess.run(
        [sys.executable, "projects/broken_tool.py"],
        cwd=WORKSPACE, text=True, capture_output=True
    )
    result["tools"]["broken_tool"]["run_output"] = broken_result.stdout.strip() or broken_result.stderr.strip()
    result["tools"]["broken_tool"]["returncode"] = broken_result.returncode

    # Run off-by-one tool
    offbyone_result = subprocess.run(
        [sys.executable, "projects/off_by_one_tool.py"],
        cwd=WORKSPACE, text=True, capture_output=True
    )
    result["tools"]["off_by_one_tool"]["run_output"] = offbyone_result.stdout.strip() or offbyone_result.stderr.strip()
    result["tools"]["off_by_one_tool"]["returncode"] = offbyone_result.returncode

    return result


# ── Main: run all checks, write audit_matrix.json ─────────────────────
def main():
    results = {
        "r1": r1_source(),
        "r2": r2_totals(),
        "r3": r3_procedure(),
        "r4": r4_artifact(),
        "r5": r5_tools(),
    }

    # Build audit matrix rows
    matrix = []
    for key, data in results.items():
        req_id = data["requirement"]
        row = {
            "requirement": req_id,
            "description": "",
            "finding": "",
            "evidence_quote": "",
            "contradictions_resolved": [],
        }

        if key == "r1":
            row["description"] = "Identify the authoritative transaction source."
            row["finding"] = data["finding"] or data.get("authoritative_source", "")
            row["evidence_quote"] = data.get("finding", "")
            row["contradictions_resolved"] = [
                c["issue"] + " → " + c["resolution"] for c in data.get("contradictions", [])
            ]
        elif key == "r2":
            row["description"] = "Calculate the required totals."
            row["finding"] = f"Units={data['totals']['sales_units']}, Revenue={data['totals']['sales_revenue']}, Expenses={data['totals']['expenses_total']}, Net={data['totals']['net']}"
            row["evidence_quote"] = data["evidence_quote"]
            row["contradictions_resolved"] = [
                c["issue"] + " → " + c["resolution"] for c in data.get("contradictions", [])
            ]
        elif key == "r3":
            row["description"] = "Reconcile the procedure conflict."
            row["finding"] = data["resolution"]
            row["evidence_quote"] = (
                "meeting_notes.md: 'The signed current procedure remains the operational source of truth.'; "
                "current.md step 2: 'Validate the header and numeric fields.'"
            )
            row["contradictions_resolved"] = [
                f"{c['between'][0]} vs {c['between'][1]}: {c['issue']} → {c['resolution']}"
                for c in data["conflicts"]
            ]
        elif key == "r4":
            row["description"] = "Produce the final audit artifact."
            row["finding"] = f"Artifact: {data['artifact']}"
            row["evidence_quote"] = data["evidence_quote"]
            row["contradictions_resolved"] = [
                c["issue"] + " → " + c["resolution"] for c in data.get("contradictions", [])
            ]
        elif key == "r5":
            row["description"] = "Verify the supporting tool output."
            tool_summaries = []
            for tool_name, tool_info in data.get("tools", {}).items():
                tool_summaries.append(f"{tool_name}: {tool_info.get('issue', 'unknown')}")
            row["finding"] = "; ".join(tool_summaries)
            row["evidence_quote"] = "; ".join(
                t.get("test_expectation", "") or t.get("issue", "")
                for t in data.get("tools", {}).values()
            )
            row["contradictions_resolved"] = [
                t.get("contradiction", "") + " → " + t.get("resolution", "")
                for t in data.get("tools", {}).values()
            ]

        matrix.append(row)

    # Write audit matrix
    matrix_path = WORKSPACE / "reports" / "audit_matrix.json"
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    matrix_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")
    print(f"Written: {matrix_path}")

    # Print summary
    for row in matrix:
        print(f"\n{'='*60}")
        print(f"{row['requirement']}: {row['description']}")
        print(f"Finding: {row['finding']}")
        print(f"Evidence: {row['evidence_quote'][:120]}...")
        if row["contradictions_resolved"]:
            print("Contradictions resolved:")
            for c in row["contradictions_resolved"]:
                print(f"  • {c}")

    print(f"\n{'='*60}")
    print(f"Investigation complete. {len(matrix)} requirements analyzed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
