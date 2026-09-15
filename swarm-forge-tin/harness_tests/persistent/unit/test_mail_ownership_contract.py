"""In-process contract tests for mail ownership, completion, and status.

The subprocess suites pin the CLI surface; these tests drive ``mailbox.main`` in
process so coverage and CRAP see the guards the tool relies on to stay durable:
a non-owner cannot complete a claimed item, mixed ownership is ambiguous, batch
takeover reassigns every item, dedup sees an in-process item, and status reports
queued detail and session.
"""

import json
import mailbox

import pytest
import wiring


@pytest.fixture(autouse=True)
def _clear_wiring_cache():
    wiring.clear_cache()
    yield
    wiring.clear_cache()


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    return root


def run(project, *args):
    return mailbox.main(
        ["--root", str(project), "--state-root", str(project / "state"), *args]
    )


def send(project, *extra, to="coder", sender="orchestrator"):
    return run(
        project, "send", "--from", sender, "--to", to, "--type", "handoff", *extra
    )


def state_items(project, role, state):
    return sorted(
        (project / "state" / "mail" / "inbox" / role / state).glob("*.json")
    )


def docs(project, role, state):
    return [json.loads(path.read_text()) for path in state_items(project, role, state)]


def test_done_refuses_a_non_owner_session(project, capsys):
    send(project, "--task", "feature/periods", "--message", "x")
    assert run(project, "pull", "--as", "coder", "--session", "session-a") == 0
    capsys.readouterr()
    assert run(project, "done", "--as", "coder", "--session", "session-b") == 2
    assert "owned by session session-a" in capsys.readouterr().err
    assert state_items(project, "coder", "in_process")


def test_done_refuses_mixed_ownership(project, capsys):
    send(project, "--task", "a", "--priority", "10", "--message", "a")
    send(project, "--task", "b", "--priority", "10", "--message", "b")
    assert run(
        project, "pull", "--as", "coder", "--mode", "batch", "--session", "session-a"
    ) == 0
    files = state_items(project, "coder", "in_process")
    assert len(files) == 2
    doc = json.loads(files[0].read_text())
    doc["owner_session"] = "session-b"
    files[0].write_text(json.dumps(doc))
    capsys.readouterr()
    assert run(project, "done", "--as", "coder", "--session", "session-a") == 2
    assert "mixed ownership" in capsys.readouterr().err


def test_batch_takeover_reassigns_every_item(project, capsys):
    send(project, "--task", "a", "--priority", "10", "--message", "a")
    send(project, "--task", "b", "--priority", "10", "--message", "b")
    assert run(
        project, "pull", "--as", "coder", "--mode", "batch", "--session", "session-a"
    ) == 0
    capsys.readouterr()
    assert run(
        project, "pull", "--as", "coder", "--mode", "batch",
        "--session", "session-b", "--takeover",
    ) == 0
    assert "COUNT: 2" in capsys.readouterr().out
    owners = {doc["owner_session"] for doc in docs(project, "coder", "in_process")}
    assert owners == {"session-b"}


def test_batch_pull_refuses_a_foreign_session(project, capsys):
    send(project, "--task", "a", "--priority", "10", "--message", "a")
    send(project, "--task", "b", "--priority", "10", "--message", "b")
    assert run(
        project, "pull", "--as", "coder", "--mode", "batch", "--session", "session-a"
    ) == 0
    capsys.readouterr()
    assert run(
        project, "pull", "--as", "coder", "--mode", "batch", "--session", "session-b"
    ) == 2
    assert "owned by session session-a" in capsys.readouterr().err


def test_pull_with_an_empty_queue_reports_no_task(project, capsys):
    assert run(project, "pull", "--as", "coder") == 0
    assert "NO_TASK" in capsys.readouterr().out


def test_status_json_reports_queued_items_and_session(project, capsys):
    send(project, "--task", "feature/periods", "--priority", "10", "--message", "x")
    capsys.readouterr()
    assert run(project, "status", "--role", "coder", "--session", "s1", "--json") == 0
    data = json.loads(capsys.readouterr().out)
    assert data["session"] == "s1"
    queued = data["roles"]["coder"]["new"]
    assert [item["task"] for item in queued] == ["feature/periods"]


def test_dedup_matches_an_in_process_item(project, capsys):
    args = ("--task", "feature/periods", "--message", "x")
    assert send(project, *args) == 0
    assert run(project, "pull", "--as", "coder") == 0
    capsys.readouterr()
    assert send(project, *args) == 0
    assert "DUPLICATE: coder" in capsys.readouterr().out
    assert len(state_items(project, "coder", "in_process")) == 1


def test_done_without_a_result_leaves_the_result_unset(project, capsys):
    send(project, "--task", "feature/periods", "--message", "x")
    assert run(project, "pull", "--as", "coder") == 0
    capsys.readouterr()
    assert run(project, "done", "--as", "coder") == 0
    completed = docs(project, "coder", "completed")
    assert completed and completed[0]["result"] is None


def test_discover_roles_includes_agent_files(project, capsys):
    agents = project / ".opencode" / "agents"
    agents.mkdir(parents=True)
    (agents / "builder.md").write_text("# Builder\n")
    assert run(project, "status", "--json") == 0
    assert "builder" in json.loads(capsys.readouterr().out)["roles"]
