from __future__ import annotations

from core import inference_setup


def test_normalize_endpoint_rejects_credentials_and_preserves_openai_prefix():
    assert inference_setup.normalize_endpoint(" http://127.0.0.1:8080/v1/ ") == (
        "http://127.0.0.1:8080/v1"
    )
    assert inference_setup.normalize_endpoint(
        "http://127.0.0.1:8082/v1/", anthropic=True
    ) == "http://127.0.0.1:8082"

    try:
        inference_setup.normalize_endpoint("http://user:secret@localhost:8080/v1")
    except ValueError as exc:
        assert "credentials" in str(exc)
    else:
        raise AssertionError("credential-bearing endpoint must be rejected")


def test_discover_openai_models_deduplicates_model_ids(monkeypatch):
    monkeypatch.setattr(
        inference_setup,
        "_request_json",
        lambda url, **kwargs: {
            "data": [
                {"id": "Ornith"},
                {"id": "Qwen"},
                {"id": "Ornith"},
                {"object": "model"},
            ]
        },
    )
    endpoint, models = inference_setup.discover_openai_models("http://localhost:8080/v1/")
    assert endpoint == "http://localhost:8080/v1"
    assert models == ("Ornith", "Qwen")


def test_probe_openai_gateway_verifies_exact_model_and_inference(monkeypatch):
    calls = []

    def fake_request(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/models"):
            return {"data": [{"id": "aios-llamacpp/Ornith"}]}
        return {
            "model": "aios-llamacpp/Ornith",
            "choices": [{"message": {"role": "assistant", "content": "OK"}}],
        }

    monkeypatch.setattr(inference_setup, "_request_json", fake_request)
    result = inference_setup.probe_openai_gateway(
        "http://localhost:8080/v1", "aios-llamacpp/Ornith"
    )
    assert result.ready is True
    assert result.resolved_model == "aios-llamacpp/Ornith"
    assert calls[1][0] == "http://localhost:8080/v1/chat/completions"
    assert calls[1][1]["body"]["model"] == "aios-llamacpp/Ornith"


def test_probe_openai_gateway_fails_before_inference_when_model_is_missing(monkeypatch):
    calls = []

    def fake_request(url, **kwargs):
        calls.append(url)
        return {"data": [{"id": "AnotherModel"}]}

    monkeypatch.setattr(inference_setup, "_request_json", fake_request)
    result = inference_setup.probe_openai_gateway("http://localhost:8080/v1", "Ornith")
    assert result.reachable is True
    assert result.model_found is False
    assert result.inference_ok is False
    assert calls == ["http://localhost:8080/v1/models"]


def test_probe_openai_gateway_keeps_malformed_endpoint_fail_closed():
    result = inference_setup.probe_openai_gateway(
        "http://user:secret@localhost:8080/v1",
        "Ornith",
    )
    assert result.ready is False
    assert result.endpoint == ""
    assert "credentials" in (result.error or "")


def test_probe_anthropic_gateway_uses_messages_api(monkeypatch):
    observed = {}

    def fake_request(url, **kwargs):
        observed["url"] = url
        observed.update(kwargs)
        return {"model": "Ornith", "content": [{"type": "text", "text": "OK"}]}

    monkeypatch.setattr(inference_setup, "_request_json", fake_request)
    result = inference_setup.probe_anthropic_gateway("http://localhost:8082/v1", "Ornith")
    assert result.ready is True
    assert observed["url"] == "http://localhost:8082/v1/messages"
    assert observed["body"]["model"] == "Ornith"
