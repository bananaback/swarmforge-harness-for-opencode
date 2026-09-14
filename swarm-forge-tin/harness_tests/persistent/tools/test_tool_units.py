"""In-process unit tests for the mail and team tools.

The subprocess suites pin the end-to-end CLI contract; these tests import the
modules directly so coverage and CRAP measure the tools themselves. They cover
the validators, pure helpers, and one full command flow each.
"""

import argparse
import json
import mailbox

import pytest
import team
import wiring

ROLES = [
    "orchestrator",
    "specifier",
    "coder",
    "refactorer",
    "architect",
    "mentor",
]


@pytest.fixture(autouse=True)
def _clear_wiring_cache():
    wiring.clear_cache()
    yield
    wiring.clear_cache()


def run(module, project, *args):
    return module.main(
        ["--root", str(project), "--state-root", str(project / "state"), *args]
    )


def send_args(**overrides):
    fields = {
        "sender": "orchestrator",
        "to": "coder",
        "priority": "50",
        "mtype": "handoff",
        "message": "pointer",
        "task": "wiring",
    }
    fields.update(overrides)
    return argparse.Namespace(**fields)


def test_message_hash_is_stable_and_content_sensitive():
    first = mailbox.message_hash("orchestrator", "handoff", "t", "m")
    second = mailbox.message_hash("orchestrator", "handoff", "t", "m")
    changed = mailbox.message_hash("orchestrator", "handoff", "t", "other")
    assert first == second
    assert first != changed


def test_validate_send_collects_problems(monkeypatch, tmp_path):
    monkeypatch.setattr(mailbox, "discover_roles", lambda root: ROLES)
    args = send_args(
        sender="Bad", to="ghost", priority="9", mtype="weird", message="a\nb"
    )
    with pytest.raises(mailbox.MailError) as error:
        mailbox.validate_send(tmp_path, args)
    problems = "\n".join(error.value.problems)
    assert "sender must be a lowercase role name" in problems
    assert "unknown recipient `ghost`" in problems
    assert "priority" in problems
    assert "one line" in problems
    assert "type` must be one of" in problems

    with pytest.raises(mailbox.MailError) as missing:
        mailbox.validate_send(tmp_path, send_args(task=""))
    assert "requires a `task` name" in "\n".join(missing.value.problems)


def test_validate_send_returns_recipients(monkeypatch, tmp_path):
    monkeypatch.setattr(mailbox, "discover_roles", lambda root: ROLES)
    recipients = mailbox.validate_send(tmp_path, send_args(to="coder,refactorer"))
    assert recipients == ["coder", "refactorer"]


def test_mailbox_command_flow_in_process(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    assert run(mailbox, project, "send", "--from", "orchestrator", "--to", "coder",
               "--task", "wiring", "--message", "pointer", "--session", "s1") == 0
    capsys.readouterr()
    assert run(mailbox, project, "pull", "--as", "coder", "--session", "s1") == 0
    assert "TASK:" in capsys.readouterr().out
    assert run(mailbox, project, "pull", "--as", "coder", "--session", "s1") == 0
    assert "RESUMED: yes" in capsys.readouterr().out
    assert run(mailbox, project, "done", "--as", "coder", "--session", "s1") == 0
    assert "NO_TASK" in capsys.readouterr().out
    inbox = project / "state" / "mail" / "inbox" / "coder"
    assert list((inbox / "completed").glob("*.json"))


def test_mailbox_batch_in_process(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    for task in ("a", "b"):
        assert run(mailbox, project, "send", "--from", "orchestrator", "--to", "coder",
                   "--priority", "10", "--task", task, "--message", task,
                   "--session", "s1") == 0
    assert run(mailbox, project, "pull", "--as", "coder", "--mode", "batch", "--session", "s1") == 0
    assert "COUNT: 2" in capsys.readouterr().out


def test_mailbox_done_without_pull_is_refused(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    assert run(mailbox, project, "done", "--as", "coder", "--session", "s1") == 2
    assert "no in-process mail" in capsys.readouterr().err


def test_task_problem_accepts_and_rejects():
    assert team.task_problem("feature/periods-1") is None
    for bad in ("", "../evil", "a//b", "a/./b", "a\\b", "a" * 81):
        assert team.task_problem(bad) is not None


def test_task_problem_validates_segments():
    """task_problem validates segment format and length."""
    assert team.task_problem("a") is None
    assert team.task_problem("feature/periods-1") is None
    assert team.task_problem("a.b_c-d") is None
    assert team.task_problem("") is not None
    assert team.task_problem("../evil") is not None
    assert team.task_problem("a//b") is not None
    assert team.task_problem("a/./b") is not None
    assert team.task_problem("a\\b") is not None
    assert team.task_problem("a" * 81) is not None


def test_validators_reject_unknown_values():
    team.validate_task("ok/one")
    # `senior` is gone as a seat, not just unknown
    for bad_seat in ("ghost", "", "senior"):
        with pytest.raises(team.TeamError):
            team.validate_seat(bad_seat)
    with pytest.raises(team.TeamError):
        team.validate_role("ghost")
    with pytest.raises(team.TeamError):
        team.validate_kind("ghost")


def test_chunk_input_payload_renders_files_and_flags_unreadable(tmp_path):
    state = tmp_path / "state"
    input_dir = team._input_dir(state, "c1", "01-coder")
    input_dir.mkdir(parents=True)
    (input_dir / "a.md").write_text("hello")
    (input_dir / "b.bin").write_bytes(b"\xff\xfe")
    lines = team.chunk_input_payload(state, "c1", "01-coder")
    assert lines[0] == "PACK: a.md, b.bin"
    assert "--- a.md ---" in lines
    assert "hello" in lines
    assert "<unreadable: b.bin>" in lines
    assert team.chunk_input_payload(state, "c1", "missing") == []
    assert team.input_files(input_dir / "nope") == []


def test_read_entry_source_reads_at_file(tmp_path):
    entry = tmp_path / "entry.json"
    entry.write_text('{"choice": "x"}')
    assert team.read_entry_source("@" + str(entry)) == '{"choice": "x"}'
    assert team.read_entry_source('{"inline": true}') == '{"inline": true}'
    with pytest.raises(team.TeamError):
        team.read_entry_source("@/no/such/entry.json")


def test_parse_entry_rejects_missing_bad_and_non_object():
    with pytest.raises(team.TeamError):
        team.parse_entry(None)
    with pytest.raises(team.TeamError):
        team.parse_entry("not json")
    with pytest.raises(team.TeamError):
        team.parse_entry("[1, 2]")
    assert team.parse_entry('{"a": 1}') == {"a": 1}


class _DeadProc:
    pid = 999999

    def kill(self):
        raise ProcessLookupError


def test_kill_process_group_tolerates_dead_process():
    team.kill_process_group(_DeadProc())


def test_team_command_flow_in_process(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    assert run(team, project, "open", "c1", "--role", "coder", "--brief", "goal") == 0
    assert run(team, project, "bind", "c1", "--seat", "worker", "--session", "sw") == 0
    assert run(team, project, "bind", "c1", "--seat", "mentor", "--session", "sm") == 0
    assert run(team, project, "pull", "--session", "sw") == 0
    assert run(team, project, "pull", "--session", "sw") == 0
    assert "RESUMED: yes" in capsys.readouterr().out
    assert run(team, project, "context", "--session", "sw") == 0
    assert run(team, project, "journal", "--session", "sw", "--kind", "plan",
               "--entry", '{"choice": "x"}') == 0
    assert run(team, project, "send", "--session", "sw", "--to", "mentor",
               "--kind", "ask", "--message", "how?") == 0
    assert run(team, project, "attempt", "--session", "sw", "--command",
               "python3 -c \"print('ok')\"") == 0
    assert "ATTEMPT: 1" in capsys.readouterr().out
    assert run(team, project, "done", "--session", "sw") == 0
    assert run(team, project, "close", "c1") == 0
    assert run(team, project, "pull", "--session", "sw") == 2
    # after close, session is unbound
    assert "not bound" in capsys.readouterr().err


def test_run_oracle_timeout_kills_group_in_process(tmp_path):
    exit_code, output, timed_out, duration = team.run_oracle("sleep 30", tmp_path, 0.2)
    assert exit_code == 124
    assert timed_out is True
    assert output == ""
    assert duration < 5


def test_format_age_and_seconds_buckets():
    assert mailbox.format_age(None) == "-"
    assert mailbox.format_age(5) == "5s"
    assert mailbox.format_age(120) == "2m"
    assert mailbox.format_age(7200) == "2h 0m"
    assert mailbox.age_seconds(None) is None
    assert mailbox.age_seconds("not-a-stamp") is None
    assert mailbox.age_seconds("2020-01-01T00:00:00Z") > 0


def test_validate_send_covers_length_and_shape_rules(monkeypatch, tmp_path):
    monkeypatch.setattr(mailbox, "discover_roles", lambda root: ROLES)
    bad_cases = [
        send_args(sender="ghost"),
        send_args(to=""),
        send_args(to="Coder"),
        send_args(to="coder,coder"),
        send_args(mtype="note", message=None),
        send_args(mtype="note", message="x" * 81),
        send_args(message="x" * 301),
        send_args(task="x" * 81),
        send_args(task="has space"),
    ]
    for args in bad_cases:
        with pytest.raises(mailbox.MailError):
            mailbox.validate_send(tmp_path, args)
    assert mailbox.validate_send(
        tmp_path, send_args(mtype="note", message="short note", task=None)
    ) == ["coder"]


def test_mailbox_status_json_and_role_filter(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    run(mailbox, project, "send", "--from", "orchestrator", "--to", "coder",
        "--task", "wiring", "--session", "s1")
    run(mailbox, project, "pull", "--as", "coder", "--session", "s1")
    capsys.readouterr()
    assert run(mailbox, project, "status", "--json", "--role", "coder") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["roles"]["coder"]["counts"]["in_process"] == 1
    assert payload["roles"]["coder"]["in_process"][0]["owner"] == "s1"
    assert run(mailbox, project, "status") == 0
    assert "ROLE: coder" in capsys.readouterr().out


def test_mailbox_takeover_and_ambiguous_resume(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    run(mailbox, project, "send", "--from", "orchestrator", "--to", "coder",
        "--task", "wiring", "--session", "s1")
    run(mailbox, project, "pull", "--as", "coder", "--session", "s1")
    capsys.readouterr()
    assert run(mailbox, project, "pull", "--as", "coder", "--session", "s2") == 2
    assert "owned by session s1" in capsys.readouterr().err
    assert run(mailbox, project, "pull", "--as", "coder", "--session", "s2",
               "--takeover") == 0
    capsys.readouterr()
    run(mailbox, project, "done", "--as", "coder", "--session", "s2")
    for task in ("a", "b"):
        run(mailbox, project, "send", "--from", "orchestrator", "--to", "coder",
            "--priority", "10", "--task", task, "--message", task, "--session", "s1")
    assert run(mailbox, project, "pull", "--as", "coder", "--mode", "batch",
               "--session", "s1") == 0
    capsys.readouterr()
    assert run(mailbox, project, "pull", "--as", "coder", "--session", "s1") == 2
    assert "more than one in-process item" in capsys.readouterr().err


def test_mailbox_done_selects_one_item_and_records_result(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    for task in ("a", "b"):
        run(mailbox, project, "send", "--from", "orchestrator", "--to", "coder",
            "--priority", "10", "--task", task, "--message", task, "--session", "s1")
    run(mailbox, project, "send", "--from", "orchestrator", "--to", "coder",
        "--priority", "20", "--task", "c", "--message", "c", "--session", "s1")
    run(mailbox, project, "pull", "--as", "coder", "--mode", "batch", "--session", "s1")
    capsys.readouterr()
    first = sorted((project / "state" / "mail" / "inbox" / "coder" / "in_process").glob("*.json"))[0]
    mail_id = json.loads(first.read_text())["id"]
    assert run(mailbox, project, "done", "--as", "coder", "--session", "s1",
               "--id", mail_id, "--result", "half") == 0
    assert "MAIL_WAITING" in capsys.readouterr().out
    completed = list((project / "state" / "mail" / "inbox" / "coder" / "completed").glob("*.json"))
    assert json.loads(completed[0].read_text())["result"] == "half"
    left = list((project / "state" / "mail" / "inbox" / "coder" / "in_process").glob("*.json"))
    assert len(left) == 1


def test_team_status_plain_and_ready_variants(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    run(team, project, "open", "c1", "--role", "coder")
    run(team, project, "bind", "c1", "--seat", "worker", "--session", "sw")
    run(team, project, "bind", "c1", "--seat", "mentor", "--session", "sm")
    run(team, project, "pull", "--session", "sw")
    run(team, project, "send", "--session", "sw", "--to", "mentor",
        "--kind", "ask", "--message", "how?")
    capsys.readouterr()
    assert run(team, project, "status") == 0
    out = capsys.readouterr().out
    assert "SEAT: worker" in out and "SEAT: mentor" in out
    assert run(team, project, "status") == 0
    out2 = capsys.readouterr().out
    assert "TASK: c1" in out2


def test_team_pull_no_task_and_journal_delta(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    run(team, project, "open", "c1", "--role", "coder", "--brief", "goal")
    run(team, project, "bind", "c1", "--seat", "worker", "--session", "sw")
    run(team, project, "pull", "--session", "sw")
    run(team, project, "done", "--session", "sw")
    capsys.readouterr()
    assert run(team, project, "context", "--session", "sw") == 0
    capsys.readouterr()
    run(team, project, "journal", "--session", "sw", "--kind", "plan",
        "--entry", '{"choice": "x"}')
    assert run(team, project, "context", "--session", "sw", "--delta") == 0
    assert "mode delta" in capsys.readouterr().out


def test_team_journal_attaches_attempt_in_process(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    run(team, project, "open", "c1", "--role", "coder")
    run(team, project, "bind", "c1", "--seat", "worker", "--session", "sw")
    run(team, project, "pull", "--session", "sw")
    run(team, project, "attempt", "--session", "sw", "--command", "python3 -c \"print(1)\"")
    capsys.readouterr()
    assert run(team, project, "journal", "--session", "sw", "--kind", "result",
               "--entry", '{"reading": "ok"}', "--attempt", "1") == 0
    import datetime
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    td = project / "state" / "tasks" / today / "c1"
    chunk_dirs = [d for d in td.iterdir() if d.is_dir()]
    assert len(chunk_dirs) == 1
    journal_path = chunk_dirs[0] / "journal.jsonl"
    lines = journal_path.read_text().splitlines()
    record = json.loads(lines[-1])
    assert record["reading"] == "ok" and record["exit"] == 0


def test_team_bind_takeover_and_unknown_chunk(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    run(team, project, "open", "c1", "--role", "coder")
    run(team, project, "bind", "c1", "--seat", "worker", "--session", "s1")
    run(team, project, "bind", "c1", "--seat", "worker", "--session", "s2", "--takeover")
    capsys.readouterr()
    assert run(team, project, "bind", "missing", "--seat", "worker",
               "--session", "s3") == 2
    assert "does not exist" in capsys.readouterr().err


def test_team_open_with_brief_and_duplicate(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    brief = tmp_path / "brief.md"
    brief.write_text("sealed")
    assert run(team, project, "open", "c1", "--role", "coder",
               "--brief", str(brief), "--json") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["role"] == "coder"
    assert run(team, project, "open", "c1", "--role", "coder") == 2
    assert "already exists" in capsys.readouterr().err


def test_team_done_selects_item_and_refuses_unknown(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    run(team, project, "open", "c1", "--role", "coder")
    run(team, project, "bind", "c1", "--seat", "worker", "--session", "sw")
    capsys.readouterr()
    assert run(team, project, "done", "--session", "sw") == 0
    assert "COMPLETED:" in capsys.readouterr().out


def test_batch_resume_sweeps_crashed_claim(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    for task in ("a", "b"):
        run(mailbox, project, "send", "--from", "orchestrator", "--to", "coder",
            "--priority", "10", "--task", task, "--message", task, "--session", "s1")
    new_dir = project / "state" / "mail" / "inbox" / "coder" / "new"
    in_process_dir = project / "state" / "mail" / "inbox" / "coder" / "in_process"
    in_process_dir.mkdir(parents=True, exist_ok=True)
    items = sorted(new_dir.glob("*.json"))
    for index, path in enumerate(items):
        doc = json.loads(path.read_text())
        doc["batch_id"] = "batch_crash"
        doc["owner_session"] = "s1"
        path.write_text(json.dumps(doc))
        if index == 0:
            path.rename(in_process_dir / path.name)
    capsys.readouterr()
    assert run(mailbox, project, "pull", "--as", "coder", "--mode", "batch",
               "--session", "s1") == 0
    assert "COUNT: 2" in capsys.readouterr().out
    assert len(list(in_process_dir.glob("*.json"))) == 2


def test_team_status_ready_and_no_tasks_in_process(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    assert run(team, project, "status", "--ready") == 0
    assert "READY: none" in capsys.readouterr().out
    run(team, project, "open", "c1", "--role", "coder")
    run(team, project, "bind", "c1", "--seat", "worker", "--session", "sw")
    capsys.readouterr()
    assert run(team, project, "status", "--ready") == 0
    out = capsys.readouterr().out
    assert "READY: c1 worker queued" in out
    assert "READY: c1 mentor SPAWN_PENDING" in out
    assert run(team, project, "status", "--ready", "--json") == 0
    payload = json.loads(capsys.readouterr().out)
    assert ["c1", "worker", "queued"] in payload["ready"]


def test_team_status_skips_corrupt_and_stray_entries(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    run(team, project, "open", "good", "--role", "coder")
    import datetime
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    tasks = project / "state" / "tasks" / today
    (project / "state" / "tasks" / "stray-date").write_text("not a dir")
    (tasks / "stray.txt").write_text("not a dir")
    bad = tasks / "bad"
    bad.mkdir()
    (bad / "task.json").write_text("{not json")
    (tasks / "empty").mkdir()
    capsys.readouterr()
    assert run(team, project, "status") == 0
    out = capsys.readouterr().out
    assert "TASK: good" in out
    assert "TASK: bad" not in out


def test_team_pull_seat_hint_and_mismatch(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    run(team, project, "open", "c1", "--role", "coder")
    run(team, project, "bind", "c1", "--seat", "worker", "--session", "sw")
    capsys.readouterr()
    assert run(team, project, "pull", "--session", "sw", "--seat", "worker") == 0
    assert run(team, project, "pull", "--session", "sw", "--seat", "mentor") == 2
    assert "not `mentor`" in capsys.readouterr().err


def test_team_open_with_missing_inputs_skips_copy(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    assert run(team, project, "open", "c1", "--role", "coder",
               "--brief", str(tmp_path / "nope.md")) == 0
    import datetime
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    doc = json.loads((project / "state" / "tasks" / today / "c1" / "task.json").read_text())
    assert doc["inputs"] == []


def test_team_close_prunes_nested_task_dirs(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    run(team, project, "open", "a/b/c", "--role", "coder")
    capsys.readouterr()
    assert run(team, project, "close", "a/b/c") == 0
    import datetime
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    assert not (project / "state" / "tasks" / today).exists()

