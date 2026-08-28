from __future__ import annotations

import json

import pytest

from core.benchmark import agentzero_client


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return json.dumps({"success": True}).encode("utf-8")


def test_agentzero_request_timeouts_follow_task_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIOS_BENCH_TASK_TIMEOUT_SECONDS", "321.5")
    assert agentzero_client._request_timeout("/api_message") == pytest.approx(321.5)
    assert agentzero_client._request_timeout("/api_log_get") == pytest.approx(15.0)

    monkeypatch.setenv("AIOS_BENCH_TASK_TIMEOUT_SECONDS", "5")
    assert agentzero_client._request_timeout("/api_terminate_chat") == pytest.approx(5.0)


def test_agentzero_request_passes_explicit_timeout_to_urlopen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[float] = []
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_API_KEY", "secret")
    monkeypatch.setenv("AIOS_BENCH_AGENTZERO_URL", "http://127.0.0.1:50001")
    monkeypatch.setenv("AIOS_BENCH_TASK_TIMEOUT_SECONDS", "44")

    def fake_urlopen(request, timeout):
        seen.append(timeout)
        return _Response()

    monkeypatch.setattr(agentzero_client.urllib.request, "urlopen", fake_urlopen)
    assert agentzero_client._request_json("/api_message", {"message": "x"}) == {"success": True}
    assert seen == [44.0]


def test_agentzero_invalid_task_timeout_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIOS_BENCH_TASK_TIMEOUT_SECONDS", "infinite-ish")
    with pytest.raises(RuntimeError, match="positive number"):
        agentzero_client._request_timeout("/api_message")
