"""Concurrency contract tests for the per-role mail and per-task team locks.

A role dispatched twice, two identical sends, and two journal appends run as
real operating-system processes against the real flock-backed CLIs. Each test
asserts the observable state the contract promises: exactly one owner, exactly
one queued item, and distinct journal sequence numbers.
"""

import json
import subprocess
import sys

from support import TOOLS, env_without_swarm, project_config, run_tool

MAILBOX = "mailbox.py"
TEAM = "team.py"


def _run_together(script, project, config, calls):
    """Start every call as its own process, then collect each result in order."""
    procs = [
        subprocess.Popen(
            [sys.executable, str(TOOLS / script), "--root", str(project), *args],
            env=env_without_swarm(SWARM_CONFIG=config),
            cwd=str(project),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for args in calls
    ]
    results = []
    for proc in procs:
        stdout, stderr = proc.communicate()
        results.append(
            subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
        )
    return results


def _inbox(project, role, state):
    return sorted(
        (project / "state" / "mail" / "inbox" / role / state).glob("*.json")
    )


def _send_args(role="coder", task="feature/periods"):
    return (
        "send", "--from", "orchestrator", "--to", role, "--type", "handoff",
        "--task", task, "--priority", "50", "--message", task,
    )


def test_simultaneous_pulls_leave_exactly_one_owner(tmp_path):
    project, config = project_config(tmp_path)
    sent = run_tool(MAILBOX, project, config, *_send_args())
    assert sent.returncode == 0, sent.stderr
    sessions = ["session-a", "session-b"]
    results = _run_together(
        MAILBOX,
        project,
        config,
        [("pull", "--as", "coder", "--session", session) for session in sessions],
    )
    winners = [session for session, result in zip(sessions, results) if result.returncode == 0]
    assert len(winners) == 1, [
        (session, result.returncode) for session, result in zip(sessions, results)
    ]
    winner = winners[0]
    loser = next(
        result for session, result in zip(sessions, results) if session != winner
    )
    assert loser.returncode == 2, loser.stdout
    assert f"owned by session {winner}" in loser.stderr, loser.stderr
    items = _inbox(project, "coder", "in_process")
    assert len(items) == 1
    assert json.loads(items[0].read_text())["owner_session"] == winner


def test_concurrent_identical_sends_queue_exactly_one_item(tmp_path):
    project, config = project_config(tmp_path)
    args = _send_args()
    results = _run_together(MAILBOX, project, config, [args, args])
    assert all(result.returncode == 0 for result in results), [
        result.stderr for result in results
    ]
    queued = [result for result in results if "QUEUED:" in result.stdout]
    assert len(queued) == 1, [result.stdout for result in results]
    assert len(_inbox(project, "coder", "new")) == 1


def test_concurrent_journal_appends_keep_distinct_sequence_numbers(tmp_path):
    project, config = project_config(tmp_path)
    opened = run_tool(
        TEAM, project, config, "open", "feature/periods", "--role", "coder"
    )
    assert opened.returncode == 0, opened.stderr
    bound = run_tool(
        TEAM, project, config, "bind", "feature/periods", "--seat", "worker",
        "--session", "s1",
    )
    assert bound.returncode == 0, bound.stderr
    calls = [
        (
            "journal", "--session", "s1", "--kind", kind,
            "--entry", json.dumps({kind: "entry"}),
        )
        for kind in ("plan", "result")
    ]
    results = _run_together(TEAM, project, config, calls)
    assert all(result.returncode == 0 for result in results), [
        result.stderr for result in results
    ]
    journal = next((project / "state" / "tasks").rglob("journal.jsonl"))
    entries = [
        json.loads(line)
        for line in journal.read_text().splitlines()
        if line.strip()
    ]
    by_kind = {entry["kind"]: entry for entry in entries}
    assert by_kind["plan"]["seq"] != by_kind["result"]["seq"], entries
