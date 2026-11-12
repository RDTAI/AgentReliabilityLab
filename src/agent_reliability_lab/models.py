"""Typed records shared by agents, environments, and evaluators."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


@dataclass(frozen=True)
class Action:
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Termination:
    status: Literal["completed", "failed", "needs_clarification"]
    message: str

    def __post_init__(self):
        if self.status not in {"completed", "failed", "needs_clarification"}:
            raise ValueError("invalid termination status")


@dataclass(frozen=True)
class AuthorizationPolicy:
    allowed_tools: tuple[str, ...]
    allowed_recipients: tuple[str, ...] = ()

    def denial(self, action: Action) -> str | None:
        if action.tool not in self.allowed_tools:
            return "tool_not_allowed"
        if (
            action.tool in {"send_email", "create_draft"}
            and action.arguments.get("recipient") not in self.allowed_recipients
        ):
            return "recipient_not_allowed"
        return None


@dataclass(frozen=True)
class TraceEvent:
    step: int
    kind: Literal["tool_call", "tool_result", "final_answer"]
    payload: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    instruction: str
    expected_state: dict[str, Any]
    max_steps: int = 12
    invariants: tuple[str, ...] = ()
    policy: AuthorizationPolicy | None = None


@dataclass
class EvaluationResult:
    task_id: str
    success: bool
    claimed_success: bool
    false_success: bool
    state_checks: dict[str, bool]
    invariant_violations: list[str]
    failure_category: str | None
    tool_calls: int
    retries: int
    trace: list[TraceEvent]
    final_answer: str
    task_completed: bool = False
    authorization_compliant: bool = True
    authorization_violations: list[dict[str, Any]] = field(default_factory=list)
    termination_status: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "success": self.success,
            "claimed_success": self.claimed_success,
            "false_success": self.false_success,
            "state_checks": self.state_checks,
            "invariant_violations": self.invariant_violations,
            "failure_category": self.failure_category,
            "tool_calls": self.tool_calls,
            "retries": self.retries,
            "final_answer": self.final_answer,
            "task_completed": self.task_completed,
            "authorization_compliant": self.authorization_compliant,
            "authorization_violations": self.authorization_violations,
            "termination_status": self.termination_status,
            "trace": [event.__dict__ for event in self.trace],
        }
