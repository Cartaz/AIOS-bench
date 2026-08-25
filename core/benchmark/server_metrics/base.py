from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MetricsSnapshot:
    available: bool
    captured_at: float = field(default_factory=time.time)
    values: dict[str, float] = field(default_factory=dict)
    error: str | None = None


class ServerMetricsClient:
    source = "unavailable"
    enabled = False

    @property
    def public_endpoint(self) -> str | None:
        return None

    def snapshot(self) -> MetricsSnapshot:
        return MetricsSnapshot(False, error="server metrics disabled")

    def delta(self, before: MetricsSnapshot, after: MetricsSnapshot) -> dict[str, Any]:
        return {
            "available": False,
            "usage_source": "unavailable",
            "trusted_for_efficiency": False,
            "error": after.error or before.error or "server metrics unavailable",
        }


class NullServerMetricsClient(ServerMetricsClient):
    pass


class OutputTokenGuard:
    """Poll a metrics counter at bounded frequency and detect generation runaway."""

    def __init__(
        self,
        client: ServerMetricsClient,
        before: MetricsSnapshot,
        limit: int | None,
        *,
        poll_interval: float = 1.0,
    ) -> None:
        self.client = client
        self.before = before
        self.limit = int(limit) if limit is not None else None
        self.poll_interval = max(0.1, float(poll_interval))
        self.last_checked = 0.0
        self.last_snapshot: MetricsSnapshot | None = None
        self.triggered = False

    @property
    def enabled(self) -> bool:
        return bool(
            self.client.enabled
            and self.before.available
            and self.limit is not None
            and self.limit > 0
        )

    def check(self) -> bool:
        if not self.enabled or self.triggered:
            return self.triggered
        now = time.monotonic()
        if now - self.last_checked < self.poll_interval:
            return False
        self.last_checked = now
        snapshot = self.client.snapshot()
        self.last_snapshot = snapshot
        usage = self.client.delta(self.before, snapshot)
        output_tokens = usage.get("output_tokens")
        if usage.get("available") and isinstance(output_tokens, (int, float)):
            if output_tokens >= int(self.limit):
                self.triggered = True
        return self.triggered
