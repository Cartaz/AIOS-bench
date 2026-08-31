from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class TaskRuntime:
    """Task-scoped benchmark service binding owned by the runner.

    Runtime services expose only environment values needed by the harness and a
    bounded idempotent cleanup callback. The benchmark, not the frontend or
    adapter, owns their lifecycle.
    """

    environment: dict[str, str] = field(default_factory=dict)
    _closer: Callable[[], None] | None = field(default=None, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._closer is not None:
            self._closer()
