# AgentReliabilityLab

An evidence-backed reliability evaluation and fault-injection platform for tool-using AI agents.

AgentReliabilityLab checks whether an agent **actually changed the environment correctly**, not merely whether its final answer sounds successful. It combines deterministic environment oracles, reproducible tool faults, trajectory invariants, failure attribution, reliability metrics, and CI regression gates.

```text
task specification
       |
       v
 agent under test ---> trace recorder
       |                    |
       v                    v
virtual office ------> invariant checks
       |                    |
       +------ state oracle-+
                            |
                            v
                 metrics + failure report
```

## Why this project?

Tool-using agents can fail silently: a tool may time out, a non-idempotent action may run twice, or the agent may report success after a failed operation. Output-only LLM judges often miss these failures. This project makes environment evidence the primary source of truth and uses semantic judges only where deterministic verification is impossible.

## v0.1 features

- Inspectable virtual office with file, contact, and email tools.
- A small adapter protocol for connecting any agent implementation.
- Full tool-call, tool-result, and final-answer trajectories.
- Deterministic fault injection: timeout, error, empty, malformed, and false-timeout responses.
- Environment-oracle verification of real side effects.
- Trajectory invariants such as no duplicate email and no unknown tool.
- Automatic failure attribution for false success, unrecovered tool failure, loops, invariant violations, and state mismatch.
- Aggregate task-success, false-success, invariant-violation, tool-call, and retry metrics.
- Machine-readable JSON reports and configurable regression gates.
- GitHub Actions tests and a fault-injected CI smoke evaluation.

## Quick start

```bash
python -m pip install -e ".[dev]"
pytest -q
agentlab --inject-fault
```

The demo writes a detailed report to `reports/demo.json` and returns a non-zero exit code if its reliability gates fail.

## Evidence-first evaluation

A task declares expected environment state using dotted paths:

```python
TaskSpec(
    task_id="email-report",
    instruction="Find report.pdf and email it to Alice.",
    expected_state={
        "sent_emails.0": {
            "recipient": "alice@example.com",
            "attachment": "reports/report.pdf",
        }
    },
    invariants=("no_duplicate_email",),
)
```

If the agent says that the email was sent but the environment contains no matching message, the run is recorded as a **false success**. If the email tool performs the side effect but returns a timeout, an unsafe blind retry creates two emails and violates `no_duplicate_email`.

## Fault injection

Faults are attached to an exact tool invocation, making every run reproducible:

```python
FaultPlan(
    [
        FaultRule(tool="search_files", call_number=1, kind="timeout"),
        FaultRule(tool="send_email", call_number=1, kind="false_timeout"),
    ]
)
```

`false_timeout` is particularly useful: the side effect succeeds but the response is lost. It tests whether an agent verifies state or blindly repeats non-idempotent actions.

## Reliability gates

```python
gates = {
    "task_success_rate": {"min": 0.95},
    "false_success_rate": {"max": 0.01},
    "invariant_violation_rate": {"max": 0.0},
}
```

These gates can fail a pull request when an agent, prompt, model, or tool implementation introduces a reliability regression.

## Roadmap

### Reliability fixes (2026-11-12)

RetryOnceAgent now enforces one retry per planned action even when consecutive
attempts time out. Previously, tracking retries by trace step allowed repeated
timeouts to consume the entire execution budget. Empty scripted plans are rejected
at construction. Regression tests cover both cases.


- YAML task suites and automatic metamorphic task variants.
- LangGraph, OpenAI Agents SDK, AutoGen, and HTTP adapters.
- SQLite-backed calendar and database tools.
- Additional faults: stale results, permission changes, schema drift, and contradictory observations.
- Baseline-versus-candidate comparison reports.
- HTML trajectory and failure-timeline visualization.
- Human labels and evidence-grounded judge evaluation.

## Scope

This is an evaluation research prototype. It runs only simulated tools and does not send real email or modify external systems.

## License

MIT
