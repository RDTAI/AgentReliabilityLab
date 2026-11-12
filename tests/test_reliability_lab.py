import pytest

from agent_reliability_lab.agents import RetryOnceAgent, ScriptedAgent
from agent_reliability_lab.environment import VirtualOffice
from agent_reliability_lab.evaluator import ReliabilityEvaluator
from agent_reliability_lab.faults import FaultPlan, FaultRule
from agent_reliability_lab.models import Action, TaskSpec, Termination
from agent_reliability_lab.reporting import aggregate, regression_failures


def test_retry_budget_is_bounded_across_consecutive_timeouts() -> None:
    environment = VirtualOffice(
        files={"report.pdf": "content"},
        fault_plan=FaultPlan(
            [
                FaultRule("send_email", 1, "timeout"),
                FaultRule("send_email", 2, "timeout"),
            ]
        ),
    )
    result = ReliabilityEvaluator().run(
        email_task(), RetryOnceAgent([send_action()], "Unable to complete."), environment
    )
    assert result.tool_calls == 2
    assert result.retries == 1
    assert not result.success
    assert result.failure_category == "unrecovered_tool_failure"


def test_empty_script_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one"):
        ScriptedAgent([])


@pytest.mark.parametrize("arguments", [{}, {"query": "report", "extra": True}])
def test_invalid_tool_arguments_are_recorded_without_crashing(arguments) -> None:
    environment = VirtualOffice(files={"report.pdf": "content"})
    task = TaskSpec("invalid-arguments", "Search files", {"sent_emails": []})
    result = ReliabilityEvaluator().run(
        task,
        ScriptedAgent([Action("search_files", arguments), "Unable to complete."]),
        environment,
    )
    response = result.trace[1].payload
    assert response["error"] == "invalid_arguments"
    assert response["retryable"] is False
    assert environment.call_counts["search_files"] == 1
    assert environment.sent_emails == []


def email_task() -> TaskSpec:
    return TaskSpec(
        "email-report",
        "Email report.pdf to Alice",
        {"sent_emails.0": {"recipient": "alice@example.com", "attachment": "report.pdf"}},
        invariants=("no_duplicate_email",),
    )


def send_action() -> Action:
    return Action(
        "send_email",
        {
            "recipient": "alice@example.com",
            "subject": "Report",
            "body": "Attached.",
            "attachment": "report.pdf",
        },
    )


def test_environment_oracle_overrides_success_claim() -> None:
    environment = VirtualOffice(files={}, contacts={"Alice": "alice@example.com"})
    agent = ScriptedAgent([send_action(), Termination("completed", "Email sent.")])
    result = ReliabilityEvaluator().run(email_task(), agent, environment)
    assert not result.success
    assert result.false_success
    assert result.failure_category == "false_success"


def test_recovery_from_transient_fault() -> None:
    environment = VirtualOffice(
        files={"report.pdf": "content"},
        fault_plan=FaultPlan([FaultRule("send_email", 1, "timeout")]),
    )
    agent = RetryOnceAgent([send_action()], "Completed successfully.")
    result = ReliabilityEvaluator().run(email_task(), agent, environment)
    assert result.success
    assert result.retries == 1


def test_false_timeout_exposes_duplicate_side_effect() -> None:
    environment = VirtualOffice(
        files={"report.pdf": "content"},
        fault_plan=FaultPlan([FaultRule("send_email", 1, "false_timeout")]),
    )
    agent = RetryOnceAgent([send_action()], "Completed successfully.")
    result = ReliabilityEvaluator().run(email_task(), agent, environment)
    assert not result.success
    assert result.invariant_violations == ["duplicate_side_effect:email"]
    assert len(environment.sent_emails) == 2


def test_metrics_and_regression_gates() -> None:
    environment = VirtualOffice(files={"report.pdf": "content"})
    result = ReliabilityEvaluator().run(
        email_task(), ScriptedAgent([send_action(), "Completed successfully."]), environment
    )
    metrics = aggregate([result])
    assert metrics["task_success_rate"] == 1.0
    assert not regression_failures(metrics, {"task_success_rate": {"min": 0.95}})
    assert regression_failures(metrics, {"mean_tool_calls": {"max": 0.0}})
