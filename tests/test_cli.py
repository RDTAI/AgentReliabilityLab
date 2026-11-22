"""Check the actual CLI process contract used by CI."""

import json
import subprocess
import sys

import pytest


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "agent_reliability_lab.cli", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_sample_budget_changes_exit_status_but_preserves_report(tmp_path):
    report = tmp_path / "report.json"
    passed = run_cli("--output", str(report), "--inject-fault")
    assert passed.returncode == 0
    report = tmp_path / "failed-run" / "report.json"
    failed = run_cli("--output", str(report), "--min-tasks", "2")
    assert failed.returncode == 1
    assert "minimum sample size 2" in failed.stdout
    payload = json.loads(report.read_text())
    assert payload["metrics"]["tasks"] == 1
    assert payload["metrics"]["task_success_rate"] == 1.0
    assert len(payload["results"]) == 1
    assert payload["results"][0]["task_id"] == "email-report"


@pytest.mark.parametrize("budget", ["0", "-1", "1.5", "many"])
def test_invalid_budget_exits_before_creating_report(tmp_path, budget):
    report = tmp_path / "report.json"
    result = run_cli("--output", str(report), "--min-tasks", budget)
    assert result.returncode == 2
    assert "must be a positive integer" in result.stderr
    assert not report.exists()


def test_failed_gate_replaces_stale_report_with_current_evidence(tmp_path):
    report = tmp_path / "report.json"
    report.write_text('{"stale": true}')
    result = run_cli("--output", str(report), "--inject-fault", "--min-tasks", "2")
    assert result.returncode == 1
    payload = json.loads(report.read_text())
    assert "stale" not in payload
    assert payload["metrics"]["tasks"] == 1
    assert payload["metrics"]["mean_retries"] == 1.0
    assert payload["results"][0]["success"] is True
