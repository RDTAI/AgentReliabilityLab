"""Evidence-backed execution, state verification, and failure attribution."""

from __future__ import annotations

from typing import Any

from .agents import Agent
from .environment import VirtualOffice
from .models import Action, EvaluationResult, TaskSpec, Termination, TraceEvent


def _path_value(state: dict[str, Any], path: str) -> Any:
    value: Any = state
    for part in path.split("."):
        try:
            if isinstance(value, list):
                value = value[int(part)]
            elif isinstance(value, dict):
                value = value[part]
            else:
                return None
        except (IndexError, KeyError, ValueError):
            return None
    return value


class ReliabilityEvaluator:
    def run(self, task: TaskSpec, agent: Agent, environment: VirtualOffice) -> EvaluationResult:
        trace: list[TraceEvent] = []
        final_answer = ""
        termination_status = "unknown"
        authorization_violations = []

        for step in range(1, task.max_steps + 1):
            decision = agent.next_action(task.instruction, trace)
            if isinstance(decision, Termination):
                final_answer = decision.message
                termination_status = decision.status
                trace.append(
                    TraceEvent(
                        step, "final_answer", {"text": final_answer, "status": termination_status}
                    )
                )
                break
            if isinstance(decision, str):
                final_answer = decision
                trace.append(TraceEvent(step, "final_answer", {"text": decision}))
                break
            if not isinstance(decision, Action):
                termination_status = "invalid_action"
                final_answer = "Agent returned an invalid action."
                break
            trace.append(
                TraceEvent(
                    step, "tool_call", {"tool": decision.tool, "arguments": decision.arguments}
                )
            )
            denial = task.policy.denial(decision) if task.policy else None
            if denial:
                authorization_violations.append(
                    {"step": step, "tool": decision.tool, "reason": denial}
                )
                response = {
                    "ok": False,
                    "error": "authorization_denied",
                    "reason": denial,
                    "retryable": False,
                }
            else:
                response = environment.call(decision.tool, decision.arguments)
            trace.append(TraceEvent(step, "tool_result", response))
        else:
            termination_status = "step_limit"
            final_answer = "Agent exceeded the step limit."

        state = environment.snapshot()
        state_checks = {
            path: self._matches(_path_value(state, path), expected)
            for path, expected in task.expected_state.items()
        }
        violations = self._check_invariants(task, trace, state)
        task_completed = bool(state_checks) and all(state_checks.values())
        success = task_completed and not violations and not authorization_violations
        claimed_success = termination_status == "completed"
        false_success = claimed_success and not task_completed
        failure_category = self._attribute_failure(success, trace, final_answer, violations)
        if authorization_violations:
            failure_category = "authorization_violation"
        elif not success and termination_status == "step_limit":
            failure_category = "step_limit"
        elif not success and claimed_success:
            failure_category = "false_success"

        calls = [event for event in trace if event.kind == "tool_call"]
        retries = sum(
            calls[index].payload == calls[index - 1].payload for index in range(1, len(calls))
        )
        return EvaluationResult(
            task_id=task.task_id,
            success=success,
            claimed_success=claimed_success,
            false_success=false_success,
            state_checks=state_checks,
            invariant_violations=violations,
            failure_category=failure_category,
            tool_calls=len(calls),
            retries=retries,
            trace=trace,
            final_answer=final_answer,
            task_completed=task_completed,
            authorization_compliant=not authorization_violations,
            authorization_violations=authorization_violations,
            termination_status=termination_status,
        )

    @staticmethod
    def _matches(actual: Any, expected: Any) -> bool:
        if isinstance(expected, dict) and isinstance(actual, dict):
            return all(actual.get(key) == value for key, value in expected.items())
        return actual == expected

    @staticmethod
    def _check_invariants(
        task: TaskSpec, trace: list[TraceEvent], state: dict[str, Any]
    ) -> list[str]:
        violations: list[str] = []
        if "no_duplicate_email" in task.invariants and len(state["sent_emails"]) > 1:
            violations.append("duplicate_side_effect:email")
        if "no_unknown_tool" in task.invariants and any(
            event.kind == "tool_result" and event.payload.get("error") == "unknown_tool"
            for event in trace
        ):
            violations.append("unknown_tool_used")
        return violations

    @staticmethod
    def _attribute_failure(
        success: bool,
        trace: list[TraceEvent],
        final_answer: str,
        violations: list[str],
    ) -> str | None:
        if success:
            return None
        if violations:
            return "invariant_violation"
        if "step limit" in final_answer.lower():
            return "non_progress_loop"
        results = [event.payload for event in trace if event.kind == "tool_result"]
        if results and results[-1].get("error"):
            return "unrecovered_tool_failure"
        return "state_mismatch"
