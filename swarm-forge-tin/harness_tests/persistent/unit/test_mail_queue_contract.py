"""Focused contract tests for the mail queue and send-validation behaviors.

These mirror the ``mail_queue`` and ``mail_validation`` Gherkin scenarios at the
CLI level: payloads, resume/takeover, batch ambiguity, completion results,
status reporting, builtin senders, and every send-validation refusal.
"""

import json

import pytest
from support import project_config, run_tool

MAILBOX = "mailbox.py"


def run(project, config, *args):
    return run_tool(MAILBOX, project, config, *args)


def send(project, config, *extra, to="coder", sender="orchestrator", mtype="handoff"):
    return run(
        project,
        config,
        "send",
        "--from",
        sender,
        "--to",
        to,
        "--type",
        mtype,
        *extra,
    )


def inbox(project, role, state):
    directory = project / "state" / "mail" / "inbox" / role / state
    return sorted(directory.glob("*.json"))


def docs(project, role, state):
    return [json.loads(path.read_text()) for path in inbox(project, role, state)]


def test_handoff_payload_names_the_task_and_carries_the_message(tmp_path):
    project, config = project_config(tmp_path)
    assert send(
        project, config, "--task", "feature/periods", "--message", "start the work"
    ).returncode == 0
    pulled = run(project, config, "pull", "--as", "coder")
    assert "TASK_NAME: feature/periods" in pulled.stdout
    assert "start the work" in pulled.stdout


def test_note_payload_is_the_message_alone(tmp_path):
    project, config = project_config(tmp_path)
    assert send(
        project, config, "--type", "note", "--message", "heads up", mtype="note"
    ).returncode == 0
    pulled = run(project, config, "pull", "--as", "coder")
    assert pulled.stdout.split("PAYLOAD:\n", 1)[1].rstrip("\n") == "heads up"


def test_batch_claim_makes_a_task_pull_ambiguous(tmp_path):
    project, config = project_config(tmp_path)
    send(project, config, "--task", "feature/alpha", "--priority", "20", "--message", "a")
    send(project, config, "--task", "feature/beta", "--priority", "20", "--message", "b")
    batch = run(project, config, "pull", "--as", "coder", "--mode", "batch")
    assert "COUNT: 2" in batch.stdout
    again = run(project, config, "pull", "--as", "coder")
    assert again.returncode == 2
    assert "more than one in-process item" in again.stderr


def test_done_records_the_result(tmp_path):
    project, config = project_config(tmp_path)
    send(project, config, "--task", "feature/periods", "--message", "x")
    run(project, config, "pull", "--as", "coder")
    done = run(project, config, "done", "--as", "coder", "--result", "green")
    assert "NO_TASK" in done.stdout
    assert docs(project, "coder", "completed")[0]["result"] == "green"


def test_status_names_every_known_role(tmp_path):
    project, config = project_config(tmp_path)
    status = run(project, config, "status")
    assert "ROLE: coder" in status.stdout
    assert "ROLE: mentor" in status.stdout


def test_takeover_reassigns_the_in_process_owner(tmp_path):
    project, config = project_config(tmp_path)
    send(project, config, "--task", "feature/periods", "--message", "x")
    run(project, config, "pull", "--as", "coder", "--session", "session-a")
    refused = run(project, config, "pull", "--as", "coder", "--session", "session-b")
    assert refused.returncode == 2
    assert "owned by session session-a" in refused.stderr
    taken = run(
        project, config, "pull", "--as", "coder", "--session", "session-b", "--takeover"
    )
    assert "RESUMED: yes" in taken.stdout
    assert docs(project, "coder", "in_process")[0]["owner_session"] == "session-b"


def test_builtin_sender_is_accepted(tmp_path):
    project, config = project_config(tmp_path)
    result = send(
        project, config, "--task", "feature/periods", "--message", "start", sender="build"
    )
    assert result.returncode == 0
    assert "QUEUED" in result.stdout


@pytest.mark.parametrize(
    ("args", "problem"),
    [
        (
            ["--from", "Orchestrator", "--to", "coder", "--task", "feature/periods"],
            "sender must be a lowercase role name",
        ),
        (
            ["--from", "orchestrator", "--to", "Coder", "--task", "feature/periods"],
            "recipient `Coder` must be a lowercase role name",
        ),
        (
            [
                "--from", "orchestrator", "--to", "coder,mentor,coder",
                "--task", "feature/periods",
            ],
            "`to` must not repeat a recipient",
        ),
        (
            [
                "--from", "orchestrator", "--to", "coder",
                "--task", "feature/periods", "--priority", "5",
            ],
            "`priority` must be two digits from 00 to 99",
        ),
        (
            ["--from", "nobody", "--to", "coder", "--task", "feature/periods"],
            "unknown sender `nobody`",
        ),
        (
            ["--from", "orchestrator", "--to", "nobody", "--task", "feature/periods"],
            "unknown recipient `nobody`",
        ),
        (
            ["--from", "orchestrator", "--to", "coder", "--task", "feature/!bad"],
            "`task` segments must start alphanumeric",
        ),
        (
            ["--from", "orchestrator", "--to", "coder", "--task", "/leading"],
            "`task` segments must start alphanumeric",
        ),
        (
            ["--from", "orchestrator", "--to", "coder", "--task", "trailing/"],
            "`task` segments must start alphanumeric",
        ),
    ],
)
def test_invalid_send_is_refused_with_its_problem(tmp_path, args, problem):
    project, config = project_config(tmp_path)
    result = run(project, config, "send", *args)
    assert result.returncode == 2
    assert problem in result.stderr
    assert not inbox(project, "coder", "new")


def test_handoff_without_a_task_is_refused(tmp_path):
    project, config = project_config(tmp_path)
    result = run(project, config, "send", "--from", "orchestrator", "--to", "coder")
    assert result.returncode == 2
    assert "`handoff` requires a `task` name" in result.stderr


def test_over_long_task_is_refused(tmp_path):
    project, config = project_config(tmp_path)
    result = run(
        project, config, "send", "--from", "orchestrator", "--to", "coder",
        "--task", "x" * 81,
    )
    assert result.returncode == 2
    assert "`task` must be at most 80 characters" in result.stderr


def test_note_without_a_message_is_refused(tmp_path):
    project, config = project_config(tmp_path)
    result = run(
        project, config, "send", "--from", "orchestrator", "--to", "coder",
        "--type", "note",
    )
    assert result.returncode == 2
    assert "`note` requires a `message`" in result.stderr


def test_over_long_note_message_is_refused(tmp_path):
    project, config = project_config(tmp_path)
    result = run(
        project, config, "send", "--from", "orchestrator", "--to", "coder",
        "--type", "note", "--message", "x" * 81,
    )
    assert result.returncode == 2
    assert "`note` message must be at most 80 characters" in result.stderr


def test_over_long_handoff_message_is_refused(tmp_path):
    project, config = project_config(tmp_path)
    result = run(
        project, config, "send", "--from", "orchestrator", "--to", "coder",
        "--task", "feature/periods", "--message", "x" * 301,
    )
    assert result.returncode == 2
    assert "`handoff` message must be at most 300 characters" in result.stderr


def test_multi_line_message_is_refused(tmp_path):
    project, config = project_config(tmp_path)
    result = run(
        project, config, "send", "--from", "orchestrator", "--to", "coder",
        "--task", "feature/periods", "--message", "first\nsecond",
    )
    assert result.returncode == 2
    assert "`message` must be one line" in result.stderr
