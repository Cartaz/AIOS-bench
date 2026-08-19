import pytest

from aios_bench.judge import _extract_json, _validate


def _valid_result() -> dict:
    criteria = {
        "correctness": 90,
        "completeness": 80,
        "problem_solving": 85,
        "efficiency": 75,
        "robustness": 80,
        "independence": 95,
        "creativity": 60,
    }
    score = sum(criteria[k] * w for k, w in {
        "correctness": 0.30, "completeness": 0.15, "problem_solving": 0.15,
        "efficiency": 0.15, "robustness": 0.10, "independence": 0.10,
        "creativity": 0.05,
    }.items())
    return {
        "score": score,
        "criteria": criteria,
        "strengths": ["correct result"],
        "weaknesses": ["could be shorter"],
        "critical_failures": [],
        "evidence": ["reports/result.md"],
        "summary": "Strong work.",
    }


def test_judge_accepts_weighted_score():
    result = _validate(_valid_result())
    assert result["score"] == 83.5


def test_judge_extracts_fenced_json():
    result = _extract_json("```json\n{" + '"score": 50' + "}\n```")
    assert result["score"] == 50


def test_judge_rejects_score_not_matching_criteria():
    result = _valid_result()
    result["score"] = 1
    with pytest.raises(ValueError, match="disagrees"):
        _validate(result)
