"""Aggregate metrics, reports, and machine-readable regression gates."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .models import EvaluationResult


def aggregate(results: list[EvaluationResult]) -> dict[str, float | int]:
    count = len(results)
    if not count:
        return {"tasks": 0}
    return {
        "tasks": count,
        "task_success_rate": sum(result.success for result in results) / count,
        "task_completion_rate": sum(result.task_completed for result in results) / count,
        "authorization_violation_rate": sum(
            not result.authorization_compliant for result in results
        )
        / count,
        "false_success_rate": sum(result.false_success for result in results) / count,
        "invariant_violation_rate": sum(bool(result.invariant_violations) for result in results)
        / count,
        "mean_tool_calls": sum(result.tool_calls for result in results) / count,
        "mean_retries": sum(result.retries for result in results) / count,
    }


def regression_failures(
    metrics: dict[str, float | int], gates: dict[str, dict[str, float]]
) -> list[str]:
    """Fail closed on missing evidence; reject malformed gate configuration."""
    for metric, policy in gates.items():
        if not policy or set(policy) - {"min", "max"}:
            raise ValueError(f"Invalid gate for {metric}: use min and/or max")
        if any(isinstance(bound, bool) or not math.isfinite(bound) for bound in policy.values()):
            raise ValueError(f"Invalid gate for {metric}: bounds must be finite numbers")
        if "min" in policy and "max" in policy and policy["min"] > policy["max"]:
            raise ValueError(f"Invalid gate for {metric}: min exceeds max")
    failures: list[str] = []
    if metrics.get("tasks") == 0:
        failures.append("No evaluation tasks: reliability gates cannot pass without evidence")
    for metric, policy in gates.items():
        if metric not in metrics:
            failures.append(f"{metric}: metric is missing")
            continue
        value = float(metrics[metric])
        if not math.isfinite(value):
            failures.append(f"{metric}: metric must be finite")
            continue
        if "min" in policy and value < policy["min"]:
            failures.append(f"{metric}={value:.4f} is below {policy['min']:.4f}")
        if "max" in policy and value > policy["max"]:
            failures.append(f"{metric}={value:.4f} is above {policy['max']:.4f}")
    return failures


def write_report(results: list[EvaluationResult], output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "metrics": aggregate(results),
        "results": [result.to_dict() for result in results],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
