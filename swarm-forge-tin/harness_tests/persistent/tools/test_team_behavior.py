"""Behavioral contract tests for the team tool (tools/team.py).

The team tool is the deterministic router the coder/refactorer/architect
sessions rely on: write-once input packs, fixed edges, single-owner claims, the
oracle attempt recorder, and cursor-based context delivery. These tests exercise
the CLI the opencode `team_*` wrappers call.

The pre-layout tool refused a pull when the `--pack` directory was edited after
open (a pack-hash check). The task_state_layout contract replaces that mutable
pack with a write-once `input/` folder: inputs are copied once at open and never
reread, so the pack-edit refusal no longer exists and its test is gone.
"""

import json
import os
import time

from support import project_config, run_tool

TEAM = "team.py"


def process_is_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def wait_for_exit(pid, deadline=10.0):
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        if not process_is_alive(pid):
            return True
        time.sleep(0.05)
    return False


def open_task(project, config, task, role="coder", *extra):
    return run_tool(TEAM, project, config, "open", task, "--role", role, *extra)


def bind(project, config, task, seat, session, *extra):
    return run_tool(
        TEAM, project, config, "bind", task, "--seat", seat, "--session", session, *extra
    )


def pull(project, config, session, *extra):
    return run_tool(TEAM, project, config, "pull", "--session", session, *extra)


def send(project, config, session, to, kind, message):
    return run_tool(
        TEAM, project, config, "send", "--session", session,
        "--to", to, "--kind", kind, "--message", message,
    )


def done(project, config, session, *extra):
    return run_tool(TEAM, project, config, "done", "--session", session, *extra)


def status(project, config, *extra):
    return run_tool(TEAM, project, config, "status", *extra)


def journal(project, config, session, kind, entry, *extra):
    return run_tool(
        TEAM, project, config, "journal", "--session", session,
        "--kind", kind, "--entry", json.dumps(entry), *extra,
    )


def task_dir(project, task="c1"):
    import datetime
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    return project / "state" / "tasks" / today / task


def test_open_creates_dated_layout_and_seeds_worker(tmp_path):
    project, config = project_config(tmp_path)
    result = open_task(project, config, "c1")
    assert result.returncode == 0, result.stderr
    assert "OPENED: c1" in result.stdout
    td = task_dir(project, "c1")
    assert td.is_dir()
    task_json = td / "task.json"
    assert task_json.is_file()
    doc = json.loads(task_json.read_text())
    assert doc["task"] == "c1"
    assert doc["sealed"] is False
    assert doc["role"] == "coder"
    assert doc["chunk"] == "01-coder"
    assert isinstance(doc["inputs"], list)
    assert "branch" in doc["git"] and "commit" in doc["git"]
    # should have one chunk folder
    chunk_dirs = [d for d in td.iterdir() if d.is_dir()]
    assert len(chunk_dirs) == 1
    chunk = chunk_dirs[0]
    assert chunk.name.endswith("-coder")
    assert (chunk / "journal.jsonl").is_file()
    assert (chunk / "input").is_dir()
    assert (chunk / "output").is_dir()


def test_open_rejects_duplicate_and_invalid_task(tmp_path):
    project, config = project_config(tmp_path)
    assert open_task(project, config, "c1").returncode == 0
    again = open_task(project, config, "c1")
    assert again.returncode == 2
    assert "already exists" in again.stderr

    bad = open_task(project, config, "../evil")
    assert bad.returncode == 2
    assert "TEAM ERROR" in bad.stderr


def test_open_copies_feature_and_ir_from_artifacts_root(tmp_path):
    project, config = project_config(tmp_path, artifacts_root="artifacts")
    feature = tmp_path / "test.feature"
    feature.write_text("Feature: Test\n  Scenario: x\n")
    artifacts = project / "artifacts"
    artifacts.mkdir()
    ir = artifacts / "test.json"
    ir.write_text('{"name": "test", "scenarios": []}')
    # a decoy next to the feature must NOT be used as the parsed IR
    (tmp_path / "test.json").write_text('{"decoy": true}')

    result = open_task(project, config, "c1", "coder", "--feature", str(feature))
    assert result.returncode == 0, result.stderr
    inp = task_dir(project, "c1") / "01-coder" / "input"
    assert (inp / "test.feature").read_text() == feature.read_text()
    assert (inp / "test.json").read_text() == ir.read_text()


def test_status_ready_reports_pending_worker_seat(tmp_path):
    project, config = project_config(tmp_path)
    open_task(project, config, "c1")
    ready = status(project, config, "--ready")
    assert ready.returncode == 0, ready.stderr
    # the autobind plugin maps coder/refactorer/architect to the worker seat
    assert "READY: c1 worker SPAWN_PENDING" in ready.stdout


def test_status_ready_sees_nested_phase_chunk(tmp_path):
    project, config = project_config(tmp_path)
    # phase chunks are named <feature>/<role>; status must not hide them
    assert open_task(project, config, "cart/refactorer", "refactorer").returncode == 0
    ready = status(project, config, "--ready")
    assert ready.returncode == 0, ready.stderr
    assert "READY: cart/refactorer worker SPAWN_PENDING" in ready.stdout


def test_status_ready_json_lists_seats(tmp_path):
    project, config = project_config(tmp_path)
    open_task(project, config, "c1")
    ready = status(project, config, "--ready", "--json")
    assert ready.returncode == 0, ready.stderr
    payload = json.loads(ready.stdout)
    assert ("c1", "worker", "SPAWN_PENDING") in [tuple(row) for row in payload["ready"]]


def test_status_reports_loaded_cursor_and_queued_seat(tmp_path):
    project, config = project_config(tmp_path)
    open_task(project, config, "c1")
    bind(project, config, "c1", "worker", "sw")
    pull(project, config, "sw")
    # a full context delivery records advice and advances the seat cursor to 2
    run_tool(TEAM, project, config, "context", "--session", "sw")
    shown = status(project, config)
    assert shown.returncode == 0, shown.stderr
    assert "SEAT: worker session sw loaded yes cursor 2" in shown.stdout
    ready = status(project, config, "--ready")
    assert "READY: c1 worker queued" in ready.stdout


def test_input_copy_is_write_once_and_ignores_source_edits(tmp_path):
    project, config = project_config(tmp_path)
    brief = tmp_path / "brief.md"
    brief.write_text("original")
    open_task(project, config, "c1", "coder", "--brief", str(brief))
    bind(project, config, "c1", "worker", "sw")
    # editing the source after open must not change the delivered input copy
    brief.write_text("edited after open")
    pulled = pull(project, config, "sw")
    assert pulled.returncode == 0, pulled.stderr
    assert "original" in pulled.stdout
    assert "edited after open" not in pulled.stdout


def test_bind_refuses_double_bind_and_takeover_rebinds(tmp_path):
    project, config = project_config(tmp_path)
    open_task(project, config, "c1")
    assert bind(project, config, "c1", "worker", "s1").returncode == 0
    refused = bind(project, config, "c1", "worker", "s2")
    assert refused.returncode == 2
    assert "already bound" in refused.stderr
    assert bind(project, config, "c1", "worker", "s2", "--takeover").returncode == 0


def test_session_cannot_serve_two_seats(tmp_path):
    project, config = project_config(tmp_path)
    open_task(project, config, "c1")
    # can't bind same session to different seats in the same task
    assert bind(project, config, "c1", "worker", "s1").returncode == 0
    clash = bind(project, config, "c1", "mentor", "s1")
    assert clash.returncode == 2
    assert "already bound" in clash.stderr


def test_pull_seeds_chunk_item_then_resumes(tmp_path):
    project, config = project_config(tmp_path)
    brief = tmp_path / "brief.md"
    brief.write_text("do the thing")
    open_task(project, config, "c1", "coder", "--brief", str(brief))
    bind(project, config, "c1", "worker", "s1")
    first = pull(project, config, "s1")
    assert first.returncode == 0, first.stderr
    assert "TASK:" in first.stdout
    assert "PACK: brief.md" in first.stdout
    assert "do the thing" in first.stdout
    second = pull(project, config, "s1")
    assert "RESUMED: yes" in second.stdout


def test_unbound_session_is_refused(tmp_path):
    project, config = project_config(tmp_path)
    open_task(project, config, "c1")
    result = pull(project, config, "ghost")
    assert result.returncode == 2
    assert "not bound to any team seat" in result.stderr


def test_context_delta_delivers_nothing_when_idle(tmp_path):
    project, config = project_config(tmp_path)
    open_task(project, config, "c1")
    bind(project, config, "c1", "worker", "sw")
    pull(project, config, "sw")
    run_tool(TEAM, project, config, "context", "--session", "sw")
    delta = run_tool(
        TEAM, project, config, "context", "--session", "sw", "--delta", "--json"
    )
    assert delta.returncode == 0, delta.stderr
    assert json.loads(delta.stdout)["delivered"] == 0


def test_send_enforces_fixed_edges(tmp_path):
    project, config = project_config(tmp_path)
    open_task(project, config, "c1")
    bind(project, config, "c1", "worker", "sw")
    bind(project, config, "c1", "mentor", "sm")
    ok = send(project, config, "sw", "mentor", "ask", "how?")
    assert ok.returncode == 0, ok.stderr
    assert "KIND: ask" in ok.stdout

    # the senior tier is gone: no seat and no escalate/decision kinds
    no_senior = send(project, config, "sw", "senior", "ask", "skip the mentor")
    assert no_senior.returncode == 2
    assert "seat must be one of" in no_senior.stderr

    wrong_kind = send(project, config, "sw", "mentor", "brief", "wrong kind")
    assert wrong_kind.returncode == 2
    assert "requires kind `ask`" in wrong_kind.stderr

    no_escalate = send(project, config, "sm", "worker", "escalate", "no senior tier")
    assert no_escalate.returncode == 2
    assert "requires kind `brief`" in no_escalate.stderr

    brief = send(project, config, "sm", "worker", "brief", "do this")
    assert brief.returncode == 0, brief.stderr


def test_pair_may_ask_and_brief_repeatedly(tmp_path):
    project, config = project_config(tmp_path)
    open_task(project, config, "c1")
    bind(project, config, "c1", "worker", "sw")
    bind(project, config, "c1", "mentor", "sm")
    for round_number in range(1, 4):
        asked = send(project, config, "sw", "mentor", "ask", f"round {round_number}?")
        assert asked.returncode == 0, asked.stderr
        briefed = send(project, config, "sm", "worker", "brief", f"do {round_number}")
        assert briefed.returncode == 0, briefed.stderr
    td = task_dir(project, "c1")
    chunk = next(d for d in td.iterdir() if d.is_dir())
    kinds = [json.loads(line)["kind"] for line in (chunk / "journal.jsonl").read_text().splitlines()]
    assert kinds.count("stuck") == 3
    assert kinds.count("advice") == 0


def test_context_full_then_delta(tmp_path):
    project, config = project_config(tmp_path)
    brief = tmp_path / "brief.md"
    brief.write_text("## TASK\nthe goal\n")
    open_task(project, config, "c1", "coder", "--brief", str(brief))
    bind(project, config, "c1", "worker", "sw")
    pull(project, config, "sw")

    delta_too_soon = run_tool(
        TEAM, project, config, "context", "--session", "sw", "--delta"
    )
    assert delta_too_soon.returncode == 2
    assert "LOAD_REQUIRED" in delta_too_soon.stderr

    # full delivery for a bound coder is the deterministic 11-section payload
    full = run_tool(TEAM, project, config, "context", "--session", "sw")
    assert full.returncode == 0, full.stderr
    assert "PACK:" not in full.stdout
    assert full.stdout.splitlines()[0] == "TASK"
    assert full.stdout.count("\nDEFINITION OF DONE") == 1
    assert "the goal" in full.stdout

    assert journal(project, config, "sw", "plan", {"choice": "shape check"}).returncode == 0
    delta = run_tool(TEAM, project, config, "context", "--session", "sw", "--delta")
    assert delta.returncode == 0, delta.stderr
    assert "mode delta" in delta.stdout
    assert "shape check" in delta.stdout


def test_journal_is_worker_only_and_attaches_attempt(tmp_path):
    project, config = project_config(tmp_path)
    open_task(project, config, "c1")
    bind(project, config, "c1", "worker", "sw")
    bind(project, config, "c1", "mentor", "sm")
    pull(project, config, "sw")

    refused = journal(project, config, "sm", "note", {"x": 1})
    assert refused.returncode == 2
    assert "only the worker seat" in refused.stderr

    attempt = run_tool(
        TEAM, project, config, "attempt", "--session", "sw",
        "--command", "python3 -c \"print('hello-attempt')\"",
    )
    assert attempt.returncode == 0, attempt.stderr
    assert "ATTEMPT: 1" in attempt.stdout
    assert "hello-attempt" in attempt.stdout

    result = run_tool(
        TEAM, project, config, "journal", "--session", "sw", "--kind", "result",
        "--entry", json.dumps({"reading": "it worked"}), "--attempt", "1",
    )
    assert result.returncode == 0, result.stderr

    td = task_dir(project, "c1")
    chunk_dirs = [d for d in td.iterdir() if d.is_dir()]
    assert len(chunk_dirs) == 1
    journal_path = chunk_dirs[0] / "journal.jsonl"
    lines = journal_path.read_text().splitlines()
    record = json.loads(lines[-1])
    assert record["reading"] == "it worked"
    assert record["cmd"] == "python3 -c \"print('hello-attempt')\""
    assert record["exit"] == 0

    unknown = run_tool(
        TEAM, project, config, "journal", "--session", "sw", "--kind", "result",
        "--entry", "{}", "--attempt", "9",
    )
    assert unknown.returncode == 2
    assert "attempt artifact not found" in unknown.stderr


def test_attempt_records_failure_exit_code(tmp_path):
    project, config = project_config(tmp_path)
    open_task(project, config, "c1")
    bind(project, config, "c1", "worker", "sw")
    pull(project, config, "sw")
    failing = run_tool(
        TEAM, project, config, "attempt", "--session", "sw",
        "--command", "python3 -c \"raise SystemExit(3)\"",
    )
    assert failing.returncode == 0, failing.stderr
    assert "EXIT: 3" in failing.stdout
    td = task_dir(project, "c1")
    chunk_dirs = [d for d in td.iterdir() if d.is_dir()]
    assert len(chunk_dirs) == 1
    output_dir = chunk_dirs[0] / "output"
    assert (output_dir / "attempt-01.txt").is_file()


def test_attempt_timeout_kills_the_whole_process_group(tmp_path):
    project, config = project_config(tmp_path)
    open_task(project, config, "c1")
    bind(project, config, "c1", "worker", "sw")
    pull(project, config, "sw")
    command = (
        "python3 -c \"import os,time;"
        "open('child.pid','w').write(str(os.getpid()));time.sleep(30)\""
    )
    result = run_tool(
        TEAM, project, config, "attempt", "--session", "sw",
        "--command", command, "--timeout", "1",
    )
    assert result.returncode == 0, result.stderr
    assert "EXIT: 124" in result.stdout
    pid = int((project / "child.pid").read_text())
    assert wait_for_exit(pid), "timed-out oracle left a live child process"


def test_close_preserves_task_to_done(tmp_path):
    project, config = project_config(tmp_path)
    open_task(project, config, "c1")
    bind(project, config, "c1", "worker", "sw")
    pull(project, config, "sw")

    td = task_dir(project, "c1")
    closed = run_tool(TEAM, project, config, "close", "c1", "--preserve")
    assert closed.returncode == 0, closed.stderr
    # task gone from live
    assert not td.is_dir()
    # task appears under done
    import datetime
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    done_dir = project / "state" / "done" / today / "c1"
    assert done_dir.is_dir()
    assert (done_dir / "task.json").is_file()


def test_close_without_preserve_deletes_task(tmp_path):
    project, config = project_config(tmp_path)
    open_task(project, config, "c1")
    bind(project, config, "c1", "worker", "sw")
    pull(project, config, "sw")

    td = task_dir(project, "c1")
    closed = run_tool(TEAM, project, config, "close", "c1")
    assert closed.returncode == 0, closed.stderr
    assert not td.is_dir()
