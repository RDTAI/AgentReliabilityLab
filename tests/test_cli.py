"""Check the actual CLI process contract used by CI."""

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
    failed = run_cli("--output", str(report), "--min-tasks", "2")
    assert failed.returncode == 1
    assert "minimum sample size 2" in failed.stdout
    assert report.exists()


@pytest.mark.parametrize("budget", ["0", "-1", "1.5", "many"])
def test_invalid_budget_exits_before_creating_report(tmp_path, budget):
    report = tmp_path / "report.json"
    result = run_cli("--output", str(report), "--min-tasks", budget)
    assert result.returncode == 2
    assert "must be a positive integer" in result.stderr
    assert not report.exists()
