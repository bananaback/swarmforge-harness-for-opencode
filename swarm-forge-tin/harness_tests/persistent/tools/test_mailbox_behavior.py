"""Behavioral contract tests for the durable mail tool (tools/mailbox.py).

These pin the invariants agents rely on for reliable communication: queue
routing, priority order, content dedup, single-owner claims, batch claims,
completion, and the status report. The CLI is the same surface the opencode
`mail_*` tool wrappers call.
"""

import json

from support import project_config, run_tool

MAILBOX = "mailbox.py"


def new_items(project, role):
    return sorted((project / "state" / "mail" / "inbox" / role / "new").glob("*.json"))


def in_process_items(project, role):
    return sorted(
        (project / "state" / "mail" / "inbox" / role / "in_process").glob("*.json")
    )


def send(project, config, *extra, to="coder", sender="orchestrator"):
    return run_tool(
        MAILBOX,
        project,
        config,
        "send",
        "--from",
        sender,
        "--to",
        to,
        *extra,
    )


def test_send_queues_one_item_per_recipient(tmp_path):
    project, config = project_config(tmp_path)
    result = send(
        project,
        config,
        "--task",
        "wiring",
        "--message",
        "pointer",
        "--session",
        "s1",
        to="coder,refactorer",
    )
    assert result.returncode == 0, result.stderr
    assert "QUEUED:" in result.stdout
    assert new_items(project, "coder")
    assert new_items(project, "refactorer")


def test_send_rejects_unknown_recipient(tmp_path):
    project, config = project_config(tmp_path)
    result = send(
        project, config, "--task", "wiring", "--message", "pointer", to="ghost"
    )
    assert result.returncode == 2
    assert "MAIL ERROR" in result.stderr
    assert not new_items(project, "ghost")


def test_send_deduplicates_identical_active_handoff(tmp_path):
    project, config = project_config(tmp_path)
    args = ("--task", "wiring", "--message", "pointer", "--session", "s1")
    assert send(project, config, *args).returncode == 0
    again = send(project, config, *args)
    assert again.returncode == 0, again.stderr
    assert "DUPLICATE: coder" in again.stdout
    assert len(new_items(project, "coder")) == 1


def test_note_requires_a_one_line_message(tmp_path):
    project, config = project_config(tmp_path)
    missing = run_tool(
        MAILBOX, project, config, "send", "--from", "orchestrator",
        "--to", "coder", "--type", "note",
    )
    assert missing.returncode == 2
    assert "note" in missing.stderr.lower()

    multiline = run_tool(
        MAILBOX, project, config, "send", "--from", "orchestrator",
        "--to", "coder", "--type", "note", "--message", "a\nb",
    )
    assert multiline.returncode == 2
    assert "one line" in multiline.stderr


def test_pull_claims_lowest_priority_number_first(tmp_path):
    project, config = project_config(tmp_path)
    send(project, config, "--task", "late", "--priority", "50", "--session", "s1")
    send(project, config, "--task", "early", "--priority", "10", "--session", "s1")
    result = run_tool(MAILBOX, project, config, "pull", "--as", "coder", "--session", "s1")
    assert result.returncode == 0, result.stderr
    assert "PRIORITY: 10" in result.stdout
    assert "TASK_NAME: early" in result.stdout


def test_pull_task_resumes_the_same_item(tmp_path):
    project, config = project_config(tmp_path)
    send(project, config, "--task", "wiring", "--session", "s1")
    first = run_tool(MAILBOX, project, config, "pull", "--as", "coder", "--session", "s1")
    second = run_tool(MAILBOX, project, config, "pull", "--as", "coder", "--session", "s1")
    assert first.returncode == 0 and second.returncode == 0
    assert "RESUMED: yes" in second.stdout
    assert first.stdout.splitlines()[0] == second.stdout.splitlines()[0]
    assert len(in_process_items(project, "coder")) == 1


def test_pull_refuses_other_session_until_takeover(tmp_path):
    project, config = project_config(tmp_path)
    send(project, config, "--task", "wiring", "--session", "s1")
    run_tool(MAILBOX, project, config, "pull", "--as", "coder", "--session", "s1")
    refused = run_tool(MAILBOX, project, config, "pull", "--as", "coder", "--session", "s2")
    assert refused.returncode == 2
    assert "owned by session s1" in refused.stderr

    taken = run_tool(
        MAILBOX, project, config, "pull", "--as", "coder", "--session", "s2", "--takeover"
    )
    assert taken.returncode == 0, taken.stderr
    assert "RESUMED: yes" in taken.stdout


def test_done_completes_and_reports_no_task(tmp_path):
    project, config = project_config(tmp_path)
    send(project, config, "--task", "wiring", "--session", "s1")
    run_tool(MAILBOX, project, config, "pull", "--as", "coder", "--session", "s1")
    done = run_tool(MAILBOX, project, config, "done", "--as", "coder", "--session", "s1")
    assert done.returncode == 0, done.stderr
    assert "COMPLETED:" in done.stdout
    assert "NO_TASK" in done.stdout
    assert not in_process_items(project, "coder")
    assert list((project / "state" / "mail" / "inbox" / "coder" / "completed").glob("*.json"))


def test_done_reports_mail_waiting_when_more_queued(tmp_path):
    project, config = project_config(tmp_path)
    send(project, config, "--task", "one", "--session", "s1")
    send(project, config, "--task", "two", "--session", "s1")
    run_tool(MAILBOX, project, config, "pull", "--as", "coder", "--session", "s1")
    done = run_tool(MAILBOX, project, config, "done", "--as", "coder", "--session", "s1")
    assert done.returncode == 0, done.stderr
    assert "MAIL_WAITING" in done.stdout


def test_batch_pull_claims_the_top_priority_group(tmp_path):
    project, config = project_config(tmp_path)
    send(project, config, "--task", "a", "--priority", "10", "--message", "ma", "--session", "s1")
    send(project, config, "--task", "b", "--priority", "10", "--message", "mb", "--session", "s1")
    send(project, config, "--task", "c", "--priority", "20", "--message", "mc", "--session", "s1")
    result = run_tool(
        MAILBOX, project, config, "pull", "--as", "coder", "--mode", "batch", "--session", "s1"
    )
    assert result.returncode == 0, result.stderr
    assert "BATCH:" in result.stdout
    assert "COUNT: 2" in result.stdout
    assert len(in_process_items(project, "coder")) == 2
    assert new_items(project, "coder")


def test_status_reports_queue_and_holder(tmp_path):
    project, config = project_config(tmp_path)
    send(project, config, "--task", "wiring", "--session", "s1")
    run_tool(MAILBOX, project, config, "pull", "--as", "coder", "--session", "s1")
    status = run_tool(MAILBOX, project, config, "status", "--role", "coder")
    assert status.returncode == 0, status.stderr
    assert "ROLE: coder" in status.stdout
    assert "IN_PROCESS: 1" in status.stdout
    assert "HOLDER:" in status.stdout
    assert "owner s1" in status.stdout


def test_mail_is_isolated_per_role(tmp_path):
    project, config = project_config(tmp_path)
    send(project, config, "--task", "wiring", "--session", "s1", to="coder")
    assert new_items(project, "coder")
    assert not new_items(project, "refactorer")


def test_identical_handoff_can_be_sent_again_after_completion(tmp_path):
    project, config = project_config(tmp_path)
    args = ("--task", "wiring", "--message", "pointer", "--session", "s1")
    assert send(project, config, *args).returncode == 0
    run_tool(MAILBOX, project, config, "pull", "--as", "coder", "--session", "s1")
    run_tool(MAILBOX, project, config, "done", "--as", "coder", "--session", "s1")
    again = send(project, config, *args)
    assert again.returncode == 0, again.stderr
    assert "QUEUED:" in again.stdout
    assert not again.stdout.strip().startswith("NO_MAIL")


def test_done_refuses_a_foreign_owner_and_names_it(tmp_path):
    project, config = project_config(tmp_path)
    send(project, config, "--task", "wiring", "--session", "session-a")
    run_tool(
        MAILBOX, project, config, "pull", "--as", "coder", "--session", "session-a"
    )
    refused = run_tool(
        MAILBOX, project, config, "done", "--as", "coder", "--session", "session-b"
    )
    assert refused.returncode == 2
    assert "owned by session session-a" in refused.stderr
    assert len(in_process_items(project, "coder")) == 1


def test_done_with_id_completes_only_the_named_item(tmp_path):
    project, config = project_config(tmp_path)
    send(project, config, "--task", "alpha", "--priority", "20", "--session", "s1")
    send(project, config, "--task", "beta", "--priority", "20", "--session", "s1")
    batch = run_tool(
        MAILBOX, project, config, "pull", "--as", "coder", "--mode", "batch"
    )
    assert batch.returncode == 0, batch.stderr
    items = in_process_items(project, "coder")
    assert len(items) == 2
    first_id = json.loads(items[0].read_text())["id"]
    done = run_tool(
        MAILBOX, project, config, "done", "--as", "coder", "--id", first_id
    )
    assert done.returncode == 0, done.stderr
    remaining = in_process_items(project, "coder")
    assert len(remaining) == 1
    assert json.loads(remaining[0].read_text())["id"] != first_id
    completed = list(
        (project / "state" / "mail" / "inbox" / "coder" / "completed").glob("*.json")
    )
    assert len(completed) == 1


def test_status_json_reports_the_holder_session(tmp_path):
    project, config = project_config(tmp_path)
    send(project, config, "--task", "wiring", "--session", "session-a")
    run_tool(
        MAILBOX, project, config, "pull", "--as", "coder", "--session", "session-a"
    )
    status = run_tool(MAILBOX, project, config, "status", "--role", "coder", "--json")
    assert status.returncode == 0, status.stderr
    holding = json.loads(status.stdout)["roles"]["coder"]["in_process"]
    assert holding and holding[0]["owner"] == "session-a"


# --- recovery: interrupted completion, corrupt items ------------------------


def test_done_without_in_process_is_refused_and_leaves_the_queue(tmp_path):
    project, config = project_config(tmp_path)
    send(project, config, "--task", "wiring", "--session", "s1")
    refused = run_tool(
        MAILBOX, project, config, "done", "--as", "coder", "--result", "green"
    )
    assert refused.returncode == 2
    assert "no in-process mail" in refused.stderr
    assert len(new_items(project, "coder")) == 1
    assert not in_process_items(project, "coder")


def test_completed_item_is_not_reclaimed_by_the_next_pull(tmp_path):
    project, config = project_config(tmp_path)
    send(project, config, "--task", "first", "--priority", "50", "--session", "s1")
    send(project, config, "--task", "second", "--priority", "50", "--session", "s1")
    run_tool(MAILBOX, project, config, "pull", "--as", "coder", "--session", "s1")
    done = run_tool(MAILBOX, project, config, "done", "--as", "coder", "--session", "s1")
    assert done.returncode == 0, done.stderr
    second = run_tool(MAILBOX, project, config, "pull", "--as", "coder", "--session", "s1")
    assert second.returncode == 0, second.stderr
    assert "TASK_NAME: second" in second.stdout


def test_pull_refuses_a_corrupt_queued_item_and_leaves_it_queued(tmp_path):
    project, config = project_config(tmp_path)
    new_dir = project / "state" / "mail" / "inbox" / "coder" / "new"
    new_dir.mkdir(parents=True)
    corrupt = new_dir / "50_corrupt.json"
    corrupt.write_text("{not json")
    refused = run_tool(MAILBOX, project, config, "pull", "--as", "coder", "--session", "s1")
    assert refused.returncode == 2
    assert "corrupt" in refused.stderr
    assert corrupt.is_file()
    assert not in_process_items(project, "coder")


def test_done_refuses_a_corrupt_in_process_item_and_leaves_it(tmp_path):
    project, config = project_config(tmp_path)
    send(project, config, "--task", "wiring", "--session", "s1")
    run_tool(MAILBOX, project, config, "pull", "--as", "coder", "--session", "s1")
    item = in_process_items(project, "coder")[0]
    item.write_text("{not json")
    refused = run_tool(
        MAILBOX, project, config, "done", "--as", "coder", "--result", "green"
    )
    assert refused.returncode == 2
    assert "corrupt" in refused.stderr
    assert item.is_file()
    completed = project / "state" / "mail" / "inbox" / "coder" / "completed"
    assert not list(completed.glob("*.json"))
