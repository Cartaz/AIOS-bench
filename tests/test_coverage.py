from core.benchmark.coverage import evaluate_set_coverage


def test_exact_coverage_is_complete() -> None:
    metrics = evaluate_set_coverage({"a", "b", "c"}, {"a", "b", "c"})

    assert metrics.true_positives == 3
    assert metrics.false_positives == 0
    assert metrics.false_negatives == 0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.completion == 1.0


def test_partial_coverage_preserves_continuous_recall() -> None:
    metrics = evaluate_set_coverage({"a", "b", "c", "d"}, {"a", "b", "c"})

    assert metrics.true_positives == 3
    assert metrics.false_positives == 0
    assert metrics.false_negatives == 1
    assert metrics.precision == 1.0
    assert metrics.recall == 0.75
    assert metrics.completion == 0.75


def test_false_positive_reduces_precision_without_weakening_recall() -> None:
    metrics = evaluate_set_coverage({"a", "b"}, {"a", "b", "decoy"})

    assert metrics.true_positives == 2
    assert metrics.false_positives == 1
    assert metrics.false_negatives == 0
    assert metrics.precision == 2 / 3
    assert metrics.recall == 1.0
    assert metrics.completion == 1.0
