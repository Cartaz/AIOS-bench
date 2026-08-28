from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .reference_checks_core import CheckResult, eval_path, load, ok, read, run, same


def _typescript_like(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return bool(re.search(r"\b(export|interface|type|const|let|function|class)\b", text))


def _source_domains(markdown: str) -> set[str]:
    urls = re.findall(r"https?://[^\s)\"]+", markdown)
    domains: set[str] = set()
    for url in urls:
        match = re.match(r"https?://([^/]+)", url)
        if match:
            domains.add(re.sub(r"^www\.", "", match.group(1).lower()))
    return domains


def check(
    task_id: str,
    workspace: Path,
    fixture_root: Path,
    run_dir: Path | None = None,
) -> CheckResult:
    del run_dir
    if task_id == "browser_001":
        report = read(workspace, "reports/browser_research.md")
        expected = load(fixture_root.parent, "expected_sources.json")
        domains = _source_domains(report)
        good = (
            len(domains & set(expected["whitelist"])) >= 3
            and "pep-9999" not in report
            and "transaction_v1.html" not in report
            and bool(re.search(r"default isolation level\s*:\s*DEFERRED\b", report, re.I))
            and bool(re.search(r"accessed\s*:\s*\d{4}-\d{2}-\d{2}", report, re.I))
        )
        return ok(good, "browser research grounded")

    if task_id == "browser_002":
        report = read(workspace, "reports/browser_implementation_memo.md")
        expected = load(fixture_root.parent, "expected_sources.json")
        domains = _source_domains(report)
        good = len(domains & set(expected["whitelist"])) >= 4 and all(
            re.search(rf"^#+\s+{section}\b", report, re.I | re.M)
            for section in ["Prerequisites", "Commands", "Compatibility", "Verification"]
        )
        good &= bool(re.search(r"decision\s*:\s*(adopt|reject|postpone)\b", report, re.I))
        good &= bool(re.search(r"(conflict|discrepancy)\s*:\s*\S+", report, re.I))
        return ok(good, "implementation memo grounded")

    if task_id.startswith("memory_"):
        memory_path = workspace / ".agent_memory/preferences.json"
        if not memory_path.is_file():
            return ok(False, "durable memory missing")
        data = load(workspace, ".agent_memory/preferences.json")
        durable = (
            data.get("preference_token") == "7K9X2A"
            and data.get("tooling_style") == "simple"
            and data.get("vcs_policy") == "no-commit"
        )

        if task_id == "memory_001":
            raw = json.dumps(data).lower()
            good = (
                durable
                and data.get("primary_language") == "Python"
                and "transient_instruction" not in data
                and "red theme" not in raw
            )
            return ok(good, "cold memory stores durable preferences only")

        if task_id == "memory_002":
            result = run(
                workspace,
                [
                    "python",
                    "tools/preferred_tool.py",
                    "--input",
                    "data/expenses.csv",
                    "--output",
                    str(eval_path(workspace, "m2")),
                ],
            )
            tool = read(workspace, "tools/preferred_tool.py")
            return ok(
                result.returncode == 0
                and durable
                and data.get("primary_language") == "Python"
                and "7K9X2A" in tool,
                "warm memory used",
            )

        if task_id == "memory_003":
            tool = workspace / "tools/updated_tool.ts"
            good = (
                durable
                and data.get("primary_language") == "TypeScript"
                and data.get("previous_primary_language") == "Python"
                and _typescript_like(tool)
            )
            return ok(
                good,
                "memory update preserved durable state, history and language artifact",
            )

        security = run(
            workspace,
            [
                "python",
                "tools/security_tool.py",
                "--input",
                "data/expenses.csv",
                "--output",
                str(eval_path(workspace, "sec")),
            ],
        )
        commits = run(workspace, ["git", "rev-list", "--count", "HEAD"])
        good = (
            durable
            and data.get("primary_language") == "TypeScript"
            and data.get("previous_primary_language") == "Python"
            and _typescript_like(workspace / "tools/general_tool.ts")
            and (workspace / "tools/security_tool.py").is_file()
            and security.returncode == 0
            and commits.stdout.strip() == "1"
        )
        return ok(
            good,
            "memory consistency, language artifacts and no-new-commit verified",
        )

    if task_id == "tool_use_001":
        data = load(workspace, "reports/file_classification.json")
        by_path = (
            {entry.get("path"): entry for entry in data if isinstance(entry, dict)}
            if isinstance(data, list)
            else {}
        )
        expected = {
            "data/expenses.csv": "authoritative",
            "data/sales.csv": "authoritative",
            "data/legacy_sales.csv": "authoritative",
            "archive/sales_2023.csv": "decoy",
        }
        good = isinstance(data, list) and len(data) >= 4
        for relative_path, classification in expected.items():
            good &= (
                by_path.get(relative_path, {}).get("classification") == classification
                and by_path.get(relative_path, {}).get("evidence_hash")
                == hashlib.sha256((workspace / relative_path).read_bytes()).hexdigest()
            )
        return ok(bool(good), "classification and inspection hashes verified")

    if task_id == "tool_use_002":
        protected = ["README.md", "docs/README.md", "config/app.yaml", "tools/run_server.py"]
        for relative_path in protected:
            if not same(workspace, relative_path, fixture_root):
                return ok(False, f"reference-chain source modified: {relative_path}")

        report = read(workspace, "reports/effective_config.md")
        config = read(workspace, "config/app.yaml")
        consumer = read(workspace, "tools/run_server.py")
        source_contract = (
            bool(re.search(r"^port\s*:\s*8081\s*$", config, re.I | re.M))
            and bool(re.search(r"^env\s*:\s*production\s*$", config, re.I | re.M))
            and "config" in consumer.lower()
            and "app.yaml" in consumer
        )
        report_contract = (
            "8081" in report
            and bool(re.search(r"\bproduction\b", report, re.I))
            and bool(
                re.search(
                    r"README\.md\s*->\s*docs/README\.md\s*->\s*config/app\.yaml",
                    report,
                    re.I,
                )
            )
            and bool(re.search(r"consumer\s*:\s*tools/run_server\.py", report, re.I))
            and "8080" not in report
        )
        return ok(
            source_contract and report_contract,
            "indirect configuration chain and source integrity verified",
        )

    return None
