from __future__ import annotations

import sys

from core import benchmark

# Tests written before the M2 package move still import the historical namespace.
# Keep the compatibility alias test-only; production code uses core.benchmark.
sys.modules.setdefault("aios_bench", benchmark)
