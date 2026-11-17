"""Regression gates must never turn absent or invalid evidence into success."""

import math

import pytest

from agent_reliability_lab.reporting import aggregate, regression_failures


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_metric_fails_even_one_sided_gate(value):
    assert regression_failures({"score": value}, {"score": {"min": 0}}) == [
        "score: metric must be finite"
    ]


def test_missing_metric_is_diagnostic_failure():
    assert regression_failures({}, {"score": {"min": 0}}) == ["score: metric is missing"]


def test_empty_evaluation_cannot_pass_empty_policy():
    assert regression_failures(aggregate([]), {})


@pytest.mark.parametrize(
    "policy",
    [{}, {"minimum": 0}, {"min": math.nan}, {"max": math.inf}, {"min": True}, {"min": 1, "max": 0}],
)
def test_invalid_policy_rejected_even_if_metric_missing(policy):
    with pytest.raises(ValueError, match="Invalid gate"):
        regression_failures({}, {"score": policy})


def test_inclusive_bounds_and_all_failures_reported():
    gates = {"score": {"min": 0.5, "max": 0.8}}
    assert not regression_failures({"score": 0.5}, gates)
    assert not regression_failures({"score": 0.8}, gates)
    failures = regression_failures(
        {"success": 0.4, "errors": 0.2},
        {"success": {"min": 0.9}, "errors": {"max": 0.1}},
    )
    assert len(failures) == 2
    assert "below" in failures[0]
    assert "above" in failures[1]


@pytest.mark.parametrize("value", [None, "0.99", True, [], {}])
def test_invalid_metric_types_return_diagnostics(value):
    assert regression_failures({"score": value}, {"score": {"min": 0}}) == [
        "score: metric must be a real number"
    ]


@pytest.mark.parametrize("policy", [None, [], {"min": "0.9"}, {"max": None}])
def test_invalid_policy_types_raise_value_error(policy):
    with pytest.raises(ValueError, match="Invalid gate"):
        regression_failures({}, {"score": policy})


@pytest.mark.parametrize("minimum", [0, -1, True, 1.5, "100"])
def test_invalid_minimum_sample_size(minimum):
    with pytest.raises(ValueError, match="min_tasks"):
        regression_failures({}, {}, min_tasks=minimum)


@pytest.mark.parametrize("count", [None, True, -1, 2.5, "100", math.nan])
def test_minimum_sample_size_requires_valid_count(count):
    assert regression_failures({"tasks": count}, {}, min_tasks=10) == [
        "tasks: a nonnegative integer task count is required"
    ]


def test_sample_size_gate_blocks_perfect_but_small_evaluation():
    gates = {"score": {"min": 0.95}}
    assert regression_failures({"score": 1.0}, gates, min_tasks=100)
    assert regression_failures({"tasks": 99, "score": 1.0}, gates, min_tasks=100) == [
        "tasks=99 is below minimum sample size 100"
    ]
    assert not regression_failures({"tasks": 100, "score": 1.0}, gates, min_tasks=100)
    assert not regression_failures({"tasks": 101, "score": 1.0}, gates, min_tasks=100)


def test_invalid_task_count_fails_without_sample_size_setting():
    assert regression_failures({"tasks": True}, {})
