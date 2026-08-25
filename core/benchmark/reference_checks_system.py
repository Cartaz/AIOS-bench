from __future__ import annotations

import hashlib
import json
import re

from .reference_checks_core import eval_path, load, ok, read, run, same


def _typescript_like(path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return bool(re.search(r"\b(export|interface|type|const|let|function|class)\b", text))


def check(t, w, fx, run_dir=None):
    if t == "browser_001":
        x = read(w, "reports/browser_research.md")
        cfg = load(fx.parent, "expected_sources.json")
        urls = re.findall(r"https?://[^\s)\"]+", x)
        domains = {
            re.sub(r"^www\.", "", re.match(r"https?://([^/]+)", url).group(1).lower())
            for url in urls
        }
        good = (
            len(domains & set(cfg["whitelist"])) >= 3
            and "pep-9999" not in x
            and "transaction_v1.html" not in x
            and bool(re.search(r"default isolation level\s*:\s*DEFERRED\b", x, re.I))
            and bool(re.search(r"accessed\s*:\s*\d{4}-\d{2}-\d{2}", x, re.I))
        )
        return ok(good, "browser research grounded")

    if t == "browser_002":
        x = read(w, "reports/browser_implementation_memo.md")
        cfg = load(fx.parent, "expected_sources.json")
        urls = re.findall(r"https?://[^\s)\"]+", x)
        domains = {
            re.sub(r"^www\.", "", re.match(r"https?://([^/]+)", url).group(1).lower())
            for url in urls
        }
        good = len(domains & set(cfg["whitelist"])) >= 4 and all(
            re.search(rf"^#+\s+{section}\b", x, re.I | re.M)
            for section in ["Prerequisites", "Commands", "Compatibility", "Verification"]
        )
        good &= bool(re.search(r"decision\s*:\s*(adopt|reject|postpone)\b", x, re.I))
        good &= bool(re.search(r"(conflict|discrepancy)\s*:\s*\S+", x, re.I))
        return ok(good, "implementation memo grounded")

    if t.startswith("memory_"):
        memory = w / ".agent_memory/preferences.json"
        if not memory.is_file():
            return ok(False, "durable memory missing")
        data = load(w, ".agent_memory/preferences.json")
        durable = (
            data.get("preference_token") == "7K9X2A"
            and data.get("tooling_style") == "simple"
            and data.get("vcs_policy") == "no-commit"
        )

        if t == "memory_001":
            raw = json.dumps(data).lower()
            good = (
                durable
                and data.get("primary_language") == "Python"
                and "transient_instruction" not in data
                and "red theme" not in raw
            )
            return ok(good, "cold memory stores durable preferences only")

        if t == "memory_002":
            result = run(
                w,
                [
                    "python",
                    "tools/preferred_tool.py",
                    "--input",
                    "data/expenses.csv",
                    "--output",
                    str(eval_path(w, "m2")),
                ],
            )
            tool = read(w, "tools/preferred_tool.py")
            return ok(
                result.returncode == 0
                and durable
                and data.get("primary_language") == "Python"
                and "7K9X2A" in tool,
                "warm memory used",
            )

        if t == "memory_003":
            tool = w / "tools/updated_tool.ts"
            good = (
                durable
                and data.get("primary_language") == "TypeScript"
                and data.get("previous_primary_language") == "Python"
                and _typescript_like(tool)
            )
            return ok(good, "memory update preserved durable state, history and language artifact")

        security = run(
            w,
            [
                "python",
                "tools/security_tool.py",
                "--input",
                "data/expenses.csv",
                "--output",
                str(eval_path(w, "sec")),
            ],
        )
        commits = run(w, ["git", "rev-list", "--count", "HEAD"])
        good = (
            durable
            and data.get("primary_language") == "TypeScript"
            and data.get("previous_primary_language") == "Python"
            and _typescript_like(w / "tools/general_tool.ts")
            and (w / "tools/security_tool.py").is_file()
            and security.returncode == 0
            and commits.stdout.strip() == "1"
        )
        return ok(good, "memory consistency, language artifacts and no-new-commit verified")

    if t == "tool_use_001":
        data = load(w, "reports/file_classification.json")
        by_path = {entry.get("path"): entry for entry in data} if isinstance(data, list) else {}
        expected = {
            "data/expenses.csv": "authoritative",
            "data/sales.csv": "authoritative",
            "data/legacy_sales.csv": "authoritative",
            "archive/sales_2023.csv": "decoy",
        }
        good = isinstance(data, list) and len(data) >= 4
        for path, classification in expected.items():
            good &= (
                by_path.get(path, {}).get("classification") == classification
                and by_path.get(path, {}).get("evidence_hash")
                == hashlib.sha256((w / path).read_bytes()).hexdigest()
            )
        return ok(bool(good), "classification and inspection hashes verified")

    if t == "tool_use_002":
        protected = ["README.md", "docs/README.md", "config/app.yaml", "tools/run_server.py"]
        for path in protected:
            if not same(w, path, fx):
                return ok(False, f"reference-chain source modified: {path}")

        x = read(w, "reports/effective_config.md")
        config = read(w, "config/app.yaml")
        consumer = read(w, "tools/run_server.py")
        source_contract = (
            bool(re.search(r"^port\s*:\s*8081\s*$", config, re.I | re.M))
            and bool(re.search(r"^env\s*:\s*production\s*$", config, re.I | re.M))
            and "config" in consumer.lower()
            and "app.yaml" in consumer
        )
        report_contract = (
            "8081" in x
            and bool(re.search(r"\bproduction\b", x, re.I))
            and bool(re.search(r"README\.md\s*->\s*docs/README\.md\s*->\s*config/app\.yaml", x, re.I))
            and bool(re.search(r"consumer\s*:\s*tools/run_server\.py", x, re.I))
            and "8080" not in x
        )
        return ok(source_contract and report_contract, "indirect configuration chain and source integrity verified")

    return None
