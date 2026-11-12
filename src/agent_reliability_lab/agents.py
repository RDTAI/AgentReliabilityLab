"""Minimal adapter contract plus deterministic agents for testing the harness."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from .models import Action, TraceEvent


class Agent(ABC):
    @abstractmethod
    def next_action(self, instruction: str, trace: Sequence[TraceEvent]) -> Action | str:
        """Return an Action or a final-answer string."""


class ScriptedAgent(Agent):
    """Deterministic adapter useful for harness validation and examples."""

    def __init__(self, script: Sequence[Action | str]) -> None:
        self.script = list(script)
        if not self.script:
            raise ValueError("script must contain at least one action or final answer")

    def next_action(self, instruction: str, trace: Sequence[TraceEvent]) -> Action | str:
        completed_calls = sum(event.kind == "tool_call" for event in trace)
        index = min(completed_calls, len(self.script) - 1)
        return self.script[index]


class RetryOnceAgent(Agent):
    """Wrap an action plan and retry the most recent retryable failure once."""

    def __init__(self, actions: Sequence[Action], final_answer: str) -> None:
        self.actions = list(actions)
        self.final_answer = final_answer
        self._position = 0
        self._retried_steps: set[int] = set()
        self._retried_actions: set[int] = set()

    def next_action(self, instruction: str, trace: Sequence[TraceEvent]) -> Action | str:
        if trace and trace[-1].kind == "tool_result":
            result = trace[-1].payload
            step = trace[-1].step
            action_index = max(0, self._position - 1)
            if result.get("retryable") and action_index not in self._retried_actions:
                self._retried_steps.add(step)
                self._retried_actions.add(action_index)
                return self.actions[max(0, self._position - 1)]
        if self._position >= len(self.actions):
            return self.final_answer
        action = self.actions[self._position]
        self._position += 1
        return action
