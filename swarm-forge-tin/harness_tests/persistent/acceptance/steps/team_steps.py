"""Step handlers for the team seat, context, mentor, oracle, and input features.

Every handler delegates to ``team.py`` through the CLI; the only parsing done
here is reading back the tool's own status and journal output, which no module
exposes in-process.
"""

import json
import re

from runtime import World

from .common import (
    _only_dir,
    _project,
    _run_team,
    _task_dir,
    _task_json,
    assert_refused,
    step_values,
)

DEFAULT_SESSIONS = {"worker": "worker-1", "mentor": "mentor-1"}
DEFAULT_TASK = "feature/periods"

_STATUS_SEAT_RE = re.compile(
    r"^SEAT: (\S+) session (\S+) loaded (yes|no) cursor (\d+)$"
)


def _sessions(world: World) -> dict[str, str]:
    return world.state.setdefault("team_sessions", dict(DEFAULT_SESSIONS))


def _session_for(world: World, seat: str) -> str:
    return _sessions(world).get(seat, f"{seat}-1")


def _task_for(world: World) -> str:
    return world.state.get("team_task", DEFAULT_TASK)


def _chunk_dir(world: World, task: str | None = None) -> "object":
    return _only_dir(_task_dir(world, task or _task_for(world)))


def _last_journal_entry(world: World, task: str | None = None) -> dict:
    journal = _chunk_dir(world, task) / "journal.jsonl"
    lines = [line for line in journal.read_text().splitlines() if line.strip()]
    assert lines, f"journal is empty: {journal}"
    return json.loads(lines[-1])


def _journal_entry(world: World, seat: str, kind: str):
    """Run the team journal command for a seat with a minimal ``kind`` entry."""
    return _run_team(
        world, "journal", "--session", _session_for(world, seat),
        "--kind", kind, "--entry", json.dumps({kind: "entry"}),
    )


def parse_status(stdout: str) -> dict[str, dict]:
    """Map each ``SEAT:`` status line to its session, load flag, and cursor."""
    seats = {}
    for line in stdout.splitlines():
        match = _STATUS_SEAT_RE.match(line.strip())
        if not match:
            continue
        seat, session, loaded, cursor = match.groups()
        seats[seat] = {
            "session": None if session == "-" else session,
            "loaded": loaded == "yes",
            "cursor": int(cursor),
        }
    return seats


def _bind(world: World, session: str, seat: str, task: str, takeover=False):
    args = ["bind", task, "--seat", seat, "--session", session]
    if takeover:
        args.append("--takeover")
    result = _run_team(world, *args)
    world.state["team_result"] = result
    if result.returncode == 0:
        _sessions(world)[seat] = session
        world.state["team_task"] = task
    return result


def _bind_or_fail(world: World, session: str, seat: str, task: str) -> None:
    result = _bind(world, session, seat, task)
    assert result.returncode == 0, result.stderr


def _status_seats(world: World) -> dict[str, dict]:
    result = _run_team(world, "status")
    assert result.returncode == 0, result.stderr
    world.state["team_status_stdout"] = result.stdout
    return parse_status(result.stdout)


def _snapshot_input(world: World) -> dict[str, bytes]:
    input_dir = _chunk_dir(world) / "input"
    return {
        path.name: path.read_bytes()
        for path in sorted(input_dir.iterdir())
        if path.is_file()
    }


# --- seat routing ----------------------------------------------------------


def _session_binds(world: World, examples: dict[str, str]) -> None:
    session, seat, task = step_values(
        examples, r'^session "([^"]*)" binds to seat "([^"]*)" of task "([^"]*)"$'
    )
    _bind(world, session, seat, task)


def _session_is_bound(world: World, examples: dict[str, str]) -> None:
    holder, other, task = step_values(
        examples,
        r'^session "([^"]*)" is bound to seat "([^"]*)" of task "([^"]*)"$',
    )
    _bind_or_fail(world, holder, other, task)


def _session_takes_over(world: World, examples: dict[str, str]) -> None:
    session, seat, task = step_values(
        examples, r'^session "([^"]*)" takes over seat "([^"]*)" of task "([^"]*)"$'
    )
    _bind(world, session, seat, task, takeover=True)


def _bind_reports(world: World, examples: dict[str, str]) -> None:
    (expected,) = step_values(examples, r'^the bind reports "([^"]*)"$')
    assert expected in world.state["team_result"].stdout


def _bind_refusal(world: World, examples: dict[str, str]) -> None:
    (problem,) = step_values(examples, r'^the bind refusal names "([^"]*)"$')
    result = world.state["team_result"]
    assert result.returncode == 2, f"bind was not refused: {result.stdout}"
    assert problem in result.stderr, result.stderr


def _worker_seat_bound(world: World, examples: dict[str, str]) -> None:
    (task,) = step_values(examples, r'^the worker seat is bound to task "([^"]*)"$')
    _bind_or_fail(world, _session_for(world, "worker"), "worker", task)


def _worker_and_mentor_bound(world: World, examples: dict[str, str]) -> None:
    (task,) = step_values(
        examples, r'^the worker and mentor seats are bound to task "([^"]*)"$'
    )
    for seat in ("worker", "mentor"):
        _bind_or_fail(world, _session_for(world, seat), seat, task)


def _mentor_seat_bound(world: World, examples: dict[str, str]) -> None:
    _bind_or_fail(
        world, _session_for(world, "mentor"), "mentor", _task_for(world)
    )


def _session_pulls(world: World, examples: dict[str, str]) -> None:
    (session,) = step_values(examples, r'^session "([^"]*)" pulls its chunk$')
    world.state["pull_result"] = _run_team(world, "pull", "--session", session)


def _session_pulls_seat(world: World, examples: dict[str, str]) -> None:
    session, seat = step_values(
        examples, r'^session "([^"]*)" pulls its chunk for the "([^"]*)" seat$'
    )
    world.state["pull_result"] = _run_team(
        world, "pull", "--session", session, "--seat", seat
    )


def _pull_refusal(world: World, examples: dict[str, str]) -> None:
    (problem,) = step_values(examples, r'^the pull refusal names "([^"]*)"$')
    result = world.state["pull_result"]
    assert result.returncode == 2, f"pull was not refused: {result.stdout}"
    assert problem in result.stderr, result.stderr


def _status_is_read(world: World, examples: dict[str, str]) -> None:
    _status_seats(world)


def _status_shows_session(world: World, examples: dict[str, str]) -> None:
    seat, session = step_values(
        examples, r'^the status shows seat "([^"]*)" held by session "([^"]*)"$'
    )
    seats = _status_seats(world)
    assert seats[seat]["session"] == session, f"{seat} holds {seats[seat]!r}"


def _status_shows_loaded(world: World, examples: dict[str, str]) -> None:
    seat, loaded, cursor = step_values(
        examples,
        r'^the status shows seat "([^"]*)" loaded "([^"]*)" with cursor "([^"]*)"$',
    )
    seats = _status_seats(world)
    assert seats[seat]["loaded"] == (loaded == "yes"), f"{seat} is {seats[seat]!r}"
    assert seats[seat]["cursor"] == int(cursor), f"{seat} is {seats[seat]!r}"


def _ready_list_is_read(world: World, examples: dict[str, str]) -> None:
    result = _run_team(world, "status", "--ready")
    assert result.returncode == 0, result.stderr
    world.state["team_ready_stdout"] = result.stdout


def _ready_list_shows(world: World, examples: dict[str, str]) -> None:
    (line,) = step_values(examples, r'^the ready list shows "([^"]*)"$')
    assert line in world.state["team_ready_stdout"], (
        f"ready list lacks {line!r}: {world.state['team_ready_stdout']!r}"
    )


# --- context delivery ------------------------------------------------------


def _worker_loads_context(world: World, examples: dict[str, str]) -> None:
    result = _run_team(world, "context", "--session", _session_for(world, "worker"))
    world.state["team_context_result"] = result


def _worker_loads_delta(world: World, examples: dict[str, str]) -> None:
    result = _run_team(
        world, "context", "--session", _session_for(world, "worker"), "--delta"
    )
    world.state["team_context_result"] = result


def _context_header(world: World, examples: dict[str, str]) -> None:
    task, seat, mode = step_values(
        examples,
        r'^the context header names task "([^"]*)" seat "([^"]*)" in "([^"]*)" mode$',
    )
    result = world.state["team_context_result"]
    assert result.returncode == 0, result.stderr
    header = f"CONTEXT: {task} seat {seat} mode {mode}"
    assert header in result.stdout, f"context lacks {header!r}: {result.stdout!r}"


def _context_carries_pack(world: World, examples: dict[str, str]) -> None:
    assert "PACK: " in world.state["team_context_result"].stdout


def _context_carries_journal(world: World, examples: dict[str, str]) -> None:
    assert "JOURNAL:" in world.state["team_context_result"].stdout


def _context_refusal(world: World, examples: dict[str, str]) -> None:
    (problem,) = step_values(examples, r'^the context refusal names "([^"]*)"$')
    result = world.state["team_context_result"]
    assert result.returncode == 2, f"context was not refused: {result.stdout}"
    assert problem in result.stderr, result.stderr


def _context_does_not_carry(world: World, examples: dict[str, str]) -> None:
    (message,) = step_values(examples, r'^the context does not carry "([^"]*)"$')
    assert message not in world.state["team_context_result"].stdout


def _delta_carries_kind(world: World, examples: dict[str, str]) -> None:
    (kind,) = step_values(
        examples, r'^the delta context carries the "([^"]*)" journal entry$'
    )
    assert f'"kind": "{kind}"' in world.state["team_context_result"].stdout


def _delta_omits_open(world: World, examples: dict[str, str]) -> None:
    assert '"kind": "open"' not in world.state["team_context_result"].stdout


def _worker_journals_entry(world: World, examples: dict[str, str]) -> None:
    (kind,) = step_values(examples, r'^the worker journals a "([^"]*)" entry$')
    result = _journal_entry(world, "worker", kind)
    assert result.returncode == 0, result.stderr


def _last_entry_records_mode(world: World, examples: dict[str, str]) -> None:
    (mode,) = step_values(examples, r'^the last journal entry records mode "([^"]*)"$')
    assert _last_journal_entry(world).get("mode") == mode


# --- mentor exchange -------------------------------------------------------


def _seat_sends(world: World, examples: dict[str, str]) -> None:
    seat, kind, message = step_values(
        examples,
        r'^the "([^"]*)" seat sends kind "([^"]*)" with message "([^"]*)"$',
    )
    other = "mentor" if seat == "worker" else "worker"
    result = _run_team(
        world, "send", "--session", _session_for(world, seat),
        "--to", other, "--kind", kind, "--message", message,
    )
    world.state["team_result"] = result


def _chunk_send_reports(world: World, examples: dict[str, str]) -> None:
    (expected,) = step_values(examples, r'^the chunk send reports "([^"]*)"$')
    assert expected in world.state["team_result"].stdout


def _chunk_send_refusal(world: World, examples: dict[str, str]) -> None:
    (problem,) = step_values(examples, r'^the chunk send refusal names "([^"]*)"$')
    result = world.state["team_result"]
    assert result.returncode == 2, f"send was not refused: {result.stdout}"
    assert problem in result.stderr, result.stderr


def _chunk_journal_ends_with(world: World, examples: dict[str, str]) -> None:
    (kind,) = step_values(examples, r'^the chunk journal ends with kind "([^"]*)"$')
    assert _last_journal_entry(world).get("kind") == kind


def _last_entry_records_message(world: World, examples: dict[str, str]) -> None:
    (message,) = step_values(
        examples, r'^the last journal entry records message "([^"]*)"$'
    )
    assert _last_journal_entry(world).get("message") == message


def _seat_finishes(world: World, examples: dict[str, str]) -> None:
    (seat,) = step_values(examples, r'^the "([^"]*)" seat finishes its chunk$')
    world.state["team_result"] = _run_team(
        world, "done", "--session", _session_for(world, seat)
    )


def _seat_calls_done_again(world: World, examples: dict[str, str]) -> None:
    (seat,) = step_values(examples, r'^the "([^"]*)" seat calls done again$')
    world.state["team_result"] = _run_team(
        world, "done", "--session", _session_for(world, seat)
    )


def _chunk_completion_reports(world: World, examples: dict[str, str]) -> None:
    (expected,) = step_values(examples, r'^the chunk completion reports "([^"]*)"$')
    assert expected in world.state["team_result"].stdout


def _task_record_corrupted(world: World, examples: dict[str, str]) -> None:
    """Write unreadable JSON into the task record to prove a bind fails closed."""
    _task_json(world).write_text("{not json")


def _mentor_sends_brief(world: World, examples: dict[str, str]) -> None:
    (message,) = step_values(examples, r'^the mentor sends a brief "([^"]*)"$')
    result = _run_team(
        world, "send", "--session", _session_for(world, "mentor"),
        "--to", "worker", "--kind", "brief", "--message", message,
    )
    assert result.returncode == 0, result.stderr


# --- oracle attempt --------------------------------------------------------


def _run_attempt(world: World, command: str, timeout: str | None = None):
    args = ["attempt", "--session", _session_for(world, "worker"), "--command", command]
    if timeout is not None:
        args += ["--timeout", timeout]
    result = _run_team(world, *args)
    world.state["team_result"] = result
    return result


def _worker_runs_oracle(world: World, examples: dict[str, str]) -> None:
    (command,) = step_values(examples, r'^the worker runs the oracle command "([^"]*)"$')
    _run_attempt(world, command)


def _worker_runs_oracle_timeout(world: World, examples: dict[str, str]) -> None:
    command, timeout = step_values(
        examples,
        r'^the worker runs the oracle command "([^"]*)" with a "([^"]*)" second timeout$',
    )
    _run_attempt(world, command, timeout)


def _worker_runs_two_oracles(world: World, examples: dict[str, str]) -> None:
    for _ in range(2):
        _run_attempt(world, "python3 -c 'print(42)'")


def _attempt_reports(world: World, examples: dict[str, str]) -> None:
    (expected,) = step_values(examples, r'^the attempt reports "([^"]*)"$')
    assert expected in world.state["team_result"].stdout


def _attempt_output_carries(world: World, examples: dict[str, str]) -> None:
    (output,) = step_values(examples, r'^the attempt output carries "([^"]*)"$')
    assert output in world.state["team_result"].stdout


def _chunk_output_holds(world: World, examples: dict[str, str]) -> None:
    (name,) = step_values(examples, r'^the chunk output holds "([^"]*)"$')
    output_dir = _chunk_dir(world) / "output"
    assert (output_dir / name).is_file(), f"{name} missing from {output_dir}"


def _chunk_output_carries(world: World, examples: dict[str, str]) -> None:
    name, output = step_values(
        examples, r'^the chunk output file "([^"]*)" carries "([^"]*)"$'
    )
    text = (_chunk_dir(world) / "output" / name).read_text()
    assert output in text, f"{name} lacks {output!r}: {text!r}"


def _workspace_dirty(world: World, examples: dict[str, str]) -> None:
    (_project(world) / ".gitkeep").write_text("uncommitted change\n")


def _journal_attaches_attempt(world: World, examples: dict[str, str]) -> None:
    kind, attempt = step_values(
        examples,
        r'^the worker journals a "([^"]*)" entry attaching attempt "([^"]*)"$',
    )
    result = _run_team(
        world, "journal", "--session", _session_for(world, "worker"),
        "--kind", kind, "--entry", json.dumps({kind: "entry"}),
        "--attempt", attempt,
    )
    world.state["team_result"] = result
    world.state["journal_result"] = result


def _last_entry_records_exit(world: World, examples: dict[str, str]) -> None:
    (exit_code,) = step_values(examples, r'^the last journal entry records exit "([^"]*)"$')
    assert _last_journal_entry(world).get("exit") == int(exit_code)


# --- write-once input ------------------------------------------------------


def _chunk_input_snapshotted(world: World, examples: dict[str, str]) -> None:
    world.state["team_input_snapshot"] = _snapshot_input(world)


def _chunk_input_matches(world: World, examples: dict[str, str]) -> None:
    assert _snapshot_input(world) == world.state["team_input_snapshot"]


def _worker_performs_operation(world: World, examples: dict[str, str]) -> None:
    (operation,) = step_values(
        examples, r'^the worker performs the "([^"]*)" operation$'
    )
    session = _session_for(world, "worker")
    task = _task_for(world)
    if operation == "pull":
        result = _run_team(world, "pull", "--session", session)
    elif operation == "context":
        result = _run_team(world, "context", "--session", session)
    elif operation == "journal":
        result = _run_team(
            world, "journal", "--session", session,
            "--kind", "plan", "--entry", json.dumps({"plan": "do it"}),
        )
    elif operation == "oracle attempt":
        result = _run_team(
            world, "attempt", "--session", session,
            "--command", "python3 -c 'print(42)'",
        )
    elif operation == "mentor ask":
        _bind_or_fail(world, _session_for(world, "mentor"), "mentor", task)
        result = _run_team(
            world, "send", "--session", session,
            "--to", "mentor", "--kind", "ask", "--message", "help",
        )
    elif operation == "done":
        result = _run_team(world, "done", "--session", session)
    else:
        raise AssertionError(f"unknown operation: {operation}")
    assert result.returncode == 0, result.stderr


def _reopen_task(world: World, examples: dict[str, str]) -> None:
    task, role = step_values(
        examples, r'^the orchestrator tries to reopen task "([^"]*)" for role "([^"]*)"$'
    )
    world.state["team_result"] = _run_team(world, "open", task, "--role", role)


def _reopen_refusal(world: World, examples: dict[str, str]) -> None:
    (problem,) = step_values(examples, r'^the reopen refusal names "([^"]*)"$')
    result = world.state["team_result"]
    assert result.returncode == 2, f"reopen was not refused: {result.stdout}"
    assert problem in result.stderr, result.stderr


def _brief_file_edited(world: World, examples: dict[str, str]) -> None:
    world.state["inputs"]["brief"].write_text("# Brief\nEdited after open.\n")


def _orchestrator_attempts_open(world: World, examples: dict[str, str]) -> None:
    task, role = step_values(
        examples,
        r'^the orchestrator attempts to open task "([^"]*)" for role "([^"]*)"$',
    )
    world.state["team_result"] = _run_team(world, "open", task, "--role", role)


def _team_refusal(world: World, examples: dict[str, str]) -> None:
    (problem,) = step_values(examples, r'^the team refusal names "([^"]*)"$')
    assert_refused(world.state["team_result"], problem, "team command")


def _mentor_journals_entry(world: World, examples: dict[str, str]) -> None:
    (kind,) = step_values(
        examples, r'^the mentor seat journals a "([^"]*)" entry$'
    )
    world.state["journal_result"] = _journal_entry(world, "mentor", kind)


HANDLERS = [
    (r'^session "([^"]*)" binds to seat "([^"]*)" of task "([^"]*)"$', _session_binds),
    (
        r'^session "([^"]*)" is bound to seat "([^"]*)" of task "([^"]*)"$',
        _session_is_bound,
    ),
    (
        r'^session "([^"]*)" takes over seat "([^"]*)" of task "([^"]*)"$',
        _session_takes_over,
    ),
    (r'^the bind reports "([^"]*)"$', _bind_reports),
    (r'^the bind refusal names "([^"]*)"$', _bind_refusal),
    (r'^the worker seat is bound to task "([^"]*)"$', _worker_seat_bound),
    (
        r'^the worker and mentor seats are bound to task "([^"]*)"$',
        _worker_and_mentor_bound,
    ),
    (r"^the mentor seat is also bound$", _mentor_seat_bound),
    (r'^session "([^"]*)" pulls its chunk$', _session_pulls),
    (r'^session "([^"]*)" pulls its chunk for the "([^"]*)" seat$', _session_pulls_seat),
    (r'^the pull refusal names "([^"]*)"$', _pull_refusal),
    (r"^status is read$", _status_is_read),
    (
        r'^the status shows seat "([^"]*)" held by session "([^"]*)"$',
        _status_shows_session,
    ),
    (
        r'^the status shows seat "([^"]*)" loaded "([^"]*)" with cursor "([^"]*)"$',
        _status_shows_loaded,
    ),
    (r"^the ready list is read$", _ready_list_is_read),
    (r'^the ready list shows "([^"]*)"$', _ready_list_shows),
    (r"^the worker loads its context$", _worker_loads_context),
    (r"^the worker loads a delta context$", _worker_loads_delta),
    (
        r'^the context header names task "([^"]*)" seat "([^"]*)" in "([^"]*)" mode$',
        _context_header,
    ),
    (r"^the context carries the input pack$", _context_carries_pack),
    (r"^the context carries the journal$", _context_carries_journal),
    (r'^the context refusal names "([^"]*)"$', _context_refusal),
    (r'^the context does not carry "([^"]*)"$', _context_does_not_carry),
    (
        r'^the delta context carries the "([^"]*)" journal entry$',
        _delta_carries_kind,
    ),
    (r'^the delta context omits the "open" journal entry$', _delta_omits_open),
    (r'^the worker journals a "([^"]*)" entry$', _worker_journals_entry),
    (r'^the last journal entry records mode "([^"]*)"$', _last_entry_records_mode),
    (
        r'^the "([^"]*)" seat sends kind "([^"]*)" with message "([^"]*)"$',
        _seat_sends,
    ),
    (r'^the chunk send reports "([^"]*)"$', _chunk_send_reports),
    (r'^the chunk send refusal names "([^"]*)"$', _chunk_send_refusal),
    (r'^the chunk journal ends with kind "([^"]*)"$', _chunk_journal_ends_with),
    (
        r'^the last journal entry records message "([^"]*)"$',
        _last_entry_records_message,
    ),
    (r'^the "([^"]*)" seat finishes its chunk$', _seat_finishes),
    (r'^the "([^"]*)" seat calls done again$', _seat_calls_done_again),
    (r'^the chunk completion reports "([^"]*)"$', _chunk_completion_reports),
    (r"^the task record is corrupted$", _task_record_corrupted),
    (r'^the mentor sends a brief "([^"]*)"$', _mentor_sends_brief),
    (r'^the worker runs the oracle command "([^"]*)"$', _worker_runs_oracle),
    (
        r'^the worker runs the oracle command "([^"]*)" with a "([^"]*)" second timeout$',
        _worker_runs_oracle_timeout,
    ),
    (r"^the worker runs two oracle commands$", _worker_runs_two_oracles),
    (r'^the attempt reports "([^"]*)"$', _attempt_reports),
    (r'^the attempt output carries "([^"]*)"$', _attempt_output_carries),
    (r'^the chunk output holds "([^"]*)"$', _chunk_output_holds),
    (r'^the chunk output file "([^"]*)" carries "([^"]*)"$', _chunk_output_carries),
    (r"^the workspace has an uncommitted change$", _workspace_dirty),
    (
        r'^the worker journals a "([^"]*)" entry attaching attempt "([^"]*)"$',
        _journal_attaches_attempt,
    ),
    (r'^the last journal entry records exit "([^"]*)"$', _last_entry_records_exit),
    (r"^the chunk input is snapshotted$", _chunk_input_snapshotted),
    (r"^the chunk input matches the snapshot$", _chunk_input_matches),
    (r'^the worker performs the "([^"]*)" operation$', _worker_performs_operation),
    (
        r'^the orchestrator tries to reopen task "([^"]*)" for role "([^"]*)"$',
        _reopen_task,
    ),
    (r'^the reopen refusal names "([^"]*)"$', _reopen_refusal),
    (r"^the given brief file is edited$", _brief_file_edited),
    (
        r'^the orchestrator attempts to open task "([^"]*)" for role "([^"]*)"$',
        _orchestrator_attempts_open,
    ),
    (r'^the team refusal names "([^"]*)"$', _team_refusal),
    (
        r'^the mentor seat journals a "([^"]*)" entry$',
        _mentor_journals_entry,
    ),
]
