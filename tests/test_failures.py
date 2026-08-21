from aios_bench.failures import (
    BLOCKED, CRASH, INFRA_ERROR, PASS, REFUSED, RUNAWAY, TIMEOUT, UNSUPPORTED, WRONG,
    classify_failure,
)


def _classify(status="failed", success=False, execution=False, evaluation=None, events=()):
    return classify_failure(
        status=status,
        success=success,
        execution_success=execution,
        evaluation_passed=evaluation,
        events=events,
    )


def test_failure_taxonomy_distinguishes_execution_and_wrong_answer():
    assert _classify(status="completed", success=True, execution=True, evaluation=True) == PASS
    assert _classify(status="failed", execution=True, evaluation=False) == WRONG
    assert _classify(status="failed", execution=False, evaluation=False) == CRASH
    assert _classify(status="timeout") == TIMEOUT
    assert _classify(status="runaway") == RUNAWAY
    assert _classify(status="error") == INFRA_ERROR
    assert _classify(status="unsupported") == UNSUPPORTED
    assert _classify(status="blocked") == BLOCKED


def test_refusal_requires_structured_evidence():
    explicit = [{"type": "refusal", "data": {"stop_reason": "safety"}}]
    assistant = [{"type": "assistant_message", "data": {"stop_reason": "refusal"}}]
    plain_text = [{"type": "assistant_message", "data": {"content": "I refuse to do this"}}]
    assert _classify(status="failed", execution=True, evaluation=False, events=explicit) == REFUSED
    assert _classify(status="failed", execution=True, evaluation=False, events=assistant) == REFUSED
    assert _classify(status="failed", execution=True, evaluation=False, events=plain_text) == WRONG
