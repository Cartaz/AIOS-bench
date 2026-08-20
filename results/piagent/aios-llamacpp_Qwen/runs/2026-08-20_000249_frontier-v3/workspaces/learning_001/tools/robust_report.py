#!/usr/bin/env python3
"""Robust reporting wrapper — same as report_cli but for robust-test scenarios."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skills.reporting_workflow import main as _workflow_main  # noqa: F401

if __name__ == "__main__":
    _workflow_main()
