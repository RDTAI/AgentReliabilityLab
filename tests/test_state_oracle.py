"""Regression cases for false passes caused by absent evidence."""

import pytest

from agent_reliability_lab import (
    ReliabilityEvaluator,
    ScriptedAgent,
    TaskSpec,
    Termination,
    VirtualOffice,
)


@pytest.mark.parametrize(
    "expected",
    [
        {"missing": None},
        {"sent_emails.0": None},
        {"files": {"missing": None}},
    ],
)
def test_absent_state_never_matches_null(expected):
    result = ReliabilityEvaluator().run(
        TaskSpec("missing-evidence", "Check state", expected),
        ScriptedAgent([Termination("completed", "Verified")]),
        VirtualOffice(),
    )
    assert not result.task_completed
    assert result.false_success


def test_present_null_is_distinct_from_absence():
    env = VirtualOffice()
    env.sent_emails.append({"attachment": None})
    result = ReliabilityEvaluator().run(
        TaskSpec("null", "Check attachment", {"sent_emails.0.attachment": None}),
        ScriptedAgent([Termination("completed", "Verified")]),
        env,
    )
    assert result.success


def test_nested_partial_dictionary_matching():
    assert ReliabilityEvaluator._matches(
        {"record": {"status": "draft", "id": 1}}, {"record": {"status": "draft"}}
    )
    assert not ReliabilityEvaluator._matches({"record": {}}, {"record": {"status": None}})


def test_negative_index_is_not_a_valid_state_path():
    env = VirtualOffice()
    env.sent_emails.append({"recipient": "alice@example.com"})
    result = ReliabilityEvaluator().run(
        TaskSpec("index", "Check state", {"sent_emails.-1": {"recipient": "alice@example.com"}}),
        ScriptedAgent([Termination("completed", "Verified")]),
        env,
    )
    assert not result.success
