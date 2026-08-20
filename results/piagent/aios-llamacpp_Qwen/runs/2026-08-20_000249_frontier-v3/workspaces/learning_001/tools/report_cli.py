#!/usr/bin/env python3
"""CLI entry-point for the reporting workflow.

Accepts --input and --output, delegates to the skills module.
"""

import argparse
import sys
from pathlib import Path

# Allow importing from the workspace root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skills.reporting_workflow import main as _workflow_main  # noqa: F401

if __name__ == "__main__":
    _workflow_main()
