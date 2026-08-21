from aios_bench.server_metrics.base import MetricsSnapshot, OutputTokenGuard, ServerMetricsClient
from aios_bench.server_metrics.llamacpp import LlamaCppMetricsClient, parse_prometheus_metrics


METRICS = """
# HELP llamacpp:prompt_tokens_total Total prompt tokens
llamacpp:prompt_tokens_total 120
llamacpp:prompt_seconds_total 2.5
llamacpp:tokens_predicted_total 45
llamacpp:tokens_predicted_seconds_total 3.0
llamacpp:requests_processing 1
llamacpp:requests_deferred 0
llamacpp:n_tokens_max 8192
"""


def test_prometheus_parser_accepts_llamacpp_colon_names():
    values = parse_prometheus_metrics(METRICS)
    assert values["prompt_tokens_total"] == 120
    assert values["tokens_predicted_total"] == 45
    assert values["n_tokens_max"] == 8192


def test_llamacpp_delta_produces_server_verified_usage():
    client = LlamaCppMetricsClient("http://127.0.0.1:8080/metrics")
    before = MetricsSnapshot(True, values={
        "prompt_tokens_total": 100,
        "prompt_seconds_total": 2.0,
        "tokens_predicted_total": 20,
        "tokens_predicted_seconds_total": 1.0,
        "requests_processing": 0,
    })
    after = MetricsSnapshot(True, values={
        "prompt_tokens_total": 150,
        "prompt_seconds_total": 2.5,
        "tokens_predicted_total": 50,
        "tokens_predicted_seconds_total": 2.5,
        "requests_processing": 0,
    })
    usage = client.delta(before, after)
    assert usage["usage_source"] == "server_verified"
    assert usage["trusted_for_efficiency"] is True
    assert usage["prompt_tokens"] == 50
    assert usage["output_tokens"] == 30
    assert usage["prompt_tokens_per_second"] == 100
    assert usage["generation_tokens_per_second"] == 20


def test_counter_reset_fails_closed():
    client = LlamaCppMetricsClient("http://127.0.0.1:8080/metrics")
    before = MetricsSnapshot(True, values={"prompt_tokens_total": 100, "tokens_predicted_total": 50})
    after = MetricsSnapshot(True, values={"prompt_tokens_total": 5, "tokens_predicted_total": 2})
    usage = client.delta(before, after)
    assert usage["available"] is False
    assert usage["trusted_for_efficiency"] is False
    assert usage["counter_reset"] is True


class FakeMetrics(ServerMetricsClient):
    source = "fake"
    enabled = True

    def __init__(self):
        self.snapshots = [
            MetricsSnapshot(True, values={"tokens": 4}),
            MetricsSnapshot(True, values={"tokens": 11}),
        ]

    def snapshot(self):
        return self.snapshots.pop(0)

    def delta(self, before, after):
        return {
            "available": True,
            "usage_source": "server_verified",
            "trusted_for_efficiency": True,
            "output_tokens": after.values["tokens"] - before.values["tokens"],
        }


def test_output_token_guard_triggers_from_server_delta():
    client = FakeMetrics()
    before = client.snapshot()
    guard = OutputTokenGuard(client, before, 7, poll_interval=0.1)
    assert guard.check() is True
    assert guard.triggered is True
