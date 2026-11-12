"""Deterministic, reproducible tool fault injection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

FaultKind = Literal["timeout", "error", "empty", "malformed", "false_timeout"]


@dataclass(frozen=True)
class FaultRule:
    tool: str
    call_number: int
    kind: FaultKind
    message: str = "injected fault"


@dataclass
class FaultPlan:
    rules: list[FaultRule] = field(default_factory=list)

    def for_call(self, tool: str, call_number: int) -> FaultRule | None:
        return next(
            (rule for rule in self.rules if rule.tool == tool and rule.call_number == call_number),
            None,
        )

    @classmethod
    def none(cls) -> FaultPlan:
        return cls([])


def injected_response(kind: FaultKind, message: str) -> dict[str, Any]:
    if kind == "timeout":
        return {"ok": False, "error": "timeout", "message": message, "retryable": True}
    if kind == "error":
        return {"ok": False, "error": "tool_error", "message": message, "retryable": False}
    if kind == "empty":
        return {"ok": True, "result": []}
    if kind == "malformed":
        return {"unexpected": message}
    raise ValueError(f"{kind} needs environment-side handling")
