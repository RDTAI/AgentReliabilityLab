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
