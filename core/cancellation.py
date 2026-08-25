from __future__ import annotations

from threading import Event


class RunCancelled(RuntimeError):
    """Raised when a user-requested benchmark cancellation reaches a safe boundary."""


class CancellationToken:
    """Thread-safe cooperative cancellation signal shared by UI and benchmark core."""

    def __init__(self) -> None:
        self._event = Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise RunCancelled("Benchmark run cancelled")
