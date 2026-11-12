"""Command-line demo and CI gate."""

from __future__ import annotations

import argparse
import json

from .agents import RetryOnceAgent
from .environment import VirtualOffice
from .evaluator import ReliabilityEvaluator
from .faults import FaultPlan, FaultRule
from .models import Action, TaskSpec, Termination
from .reporting import aggregate, regression_failures, write_report


def demo(output: str, inject_fault: bool) -> int:
    faults = (
        FaultPlan([FaultRule("search_files", 1, "timeout")]) if inject_fault else FaultPlan.none()
    )
    environment = VirtualOffice(
        files={"reports/report.pdf": "quarterly reliability report"},
        contacts={"Alice": "alice@example.com"},
        fault_plan=faults,
    )
    task = TaskSpec(
        task_id="email-report",
        instruction="Find report.pdf and email it to Alice.",
        expected_state={
            "sent_emails.0": {
                "recipient": "alice@example.com",
                "attachment": "reports/report.pdf",
            }
        },
        invariants=("no_duplicate_email", "no_unknown_tool"),
    )
    agent = RetryOnceAgent(
        [
            Action("search_files", {"query": "report.pdf"}),
            Action("lookup_contact", {"name": "Alice"}),
            Action(
                "send_email",
                {
                    "recipient": "alice@example.com",
                    "subject": "Reliability report",
                    "body": "Please find the report attached.",
                    "attachment": "reports/report.pdf",
                },
            ),
        ],
        Termination("completed", "The report was sent to Alice."),
    )
    result = ReliabilityEvaluator().run(task, agent, environment)
    write_report([result], output)
    metrics = aggregate([result])
    print(json.dumps(metrics, indent=2))
    failures = regression_failures(
        metrics,
        {"task_success_rate": {"min": 1.0}, "false_success_rate": {"max": 0.0}},
    )
    if failures:
        print("Regression gate failed:")
        print("\n".join(f"- {failure}" for failure in failures))
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate tool-using agent reliability")
    parser.add_argument("--output", default="reports/demo.json")
    parser.add_argument("--inject-fault", action="store_true")
    args = parser.parse_args()
    raise SystemExit(demo(args.output, args.inject_fault))


if __name__ == "__main__":
    main()
