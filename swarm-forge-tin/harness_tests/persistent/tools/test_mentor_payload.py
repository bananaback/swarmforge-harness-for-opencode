"""Unit tests for the deterministic mentor payload delivered by ``team_context``.

A bound mentor calls ``team_context`` and receives a system prompt followed by
exactly five sections -- GOAL, RULES, TRAIL, ASK, FAILURE -- assembled from the
task record and the worker journal. These tests pin the section shape, each
section's source and fallback, the worker-only TRAIL filter, the no-model
property, and the stability that makes a resumed mentor session deterministic.
"""

import datetime
import json
from unittest import mock

import pytest
import team
import wiring
from support import project_config, run_tool

TEAM = "team.py"

MENTOR_HEADERS = ["GOAL", "RULES", "TRAIL", "ASK", "FAILURE"]


@pytest.fixture(autouse=True)
def _clear_wiring_cache():
    wiring.clear_cache()
    yield
    wiring.clear_cache()


def task_dir(project, task="m1"):
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    return project / "state" / "tasks" / today / task


def open_mentor(project, config, state_root, task="m1", *extra):
    return run_tool(
        TEAM, project, config, "open", task, "--role", "mentor", *extra,
        state_root=state_root,
    )


def bind(project, config, state_root, seat, session, task="m1"):
    return run_tool(
        TEAM, project, config, "bind", task, "--seat", seat, "--session", session,
        state_root=state_root,
    )


def context(project, config, state_root, session="mentor-1", *extra):
    return run_tool(
        TEAM, project, config, "context", "--session", session, *extra,
        state_root=state_root,
    )


def journal(project, config, state_root, session, kind, entry, *extra):
    return run_tool(
        TEAM, project, config, "journal", "--session", session, "--kind", kind,
        "--entry", json.dumps(entry), *extra, state_root=state_root,
    )


def send(project, config, state_root, session, to, kind, message):
    return run_tool(
        TEAM, project, config, "send", "--session", session, "--to", to,
        "--kind", kind, "--message", message, state_root=state_root,
    )


def payload_headers(text):
    return [line.strip() for line in text.splitlines() if line.strip() in MENTOR_HEADERS]


def payload_section(text, header):
    lines = text.splitlines()
    start = lines.index(header) + 1
    body = []
    for line in lines[start:]:
        if line.strip() in MENTOR_HEADERS:
            break
        body.append(line)
    return "\n".join(body)


def mentor_task_doc(goal="g", rules="r", ask="", failure=""):
    return {
        "task": "m1",
        "role": "mentor",
        "chunk": "01-mentor",
        "mentor": {"goal": goal, "rules": rules, "ask": ask, "failure": failure},
    }


# --- feature scenarios 1 and 2: system prompt then five fixed sections ------


def test_payload_leads_with_system_prompt_and_has_five_sections(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_mentor(
        project, config, state_root, "m1", "--goal", "g", "--rules", "r"
    ).returncode == 0
    assert bind(project, config, state_root, "mentor", "mentor-1").returncode == 0

    result = context(project, config, state_root)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith(team.MENTOR_SYSTEM_PROMPT)
    assert payload_headers(result.stdout) == MENTOR_HEADERS
    assert len(payload_headers(result.stdout)) == 5


# --- feature scenario 3: GOAL/RULES/ASK come from task.json mentor ----------


@pytest.mark.parametrize(
    "flag,section,value",
    [
        ("--goal", "GOAL", "fix the failing acceptance tests"),
        ("--rules", "RULES", "never edit the feature file"),
        ("--ask", "ASK", "why does the parser reject this?"),
    ],
)
def test_section_carries_the_task_json_value(tmp_path, flag, section, value):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_mentor(project, config, state_root, "m1", flag, value).returncode == 0
    assert bind(project, config, state_root, "mentor", "mentor-1").returncode == 0

    result = context(project, config, state_root)
    assert result.returncode == 0, result.stderr
    assert payload_section(result.stdout, section) == value


# --- feature scenario 4: TRAIL lists worker entries in order ----------------


def test_trail_lists_worker_entries_in_order_and_excludes_tool_kinds(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_mentor(project, config, state_root, "m1", "--ask", "explicit ask").returncode == 0
    assert bind(project, config, state_root, "worker", "worker-1").returncode == 0
    assert bind(project, config, state_root, "mentor", "mentor-1").returncode == 0

    assert journal(
        project, config, state_root, "worker-1", "readback", {"readback": "R1"}
    ).returncode == 0
    assert journal(
        project, config, state_root, "worker-1", "plan", {"plan": "P2"}
    ).returncode == 0
    assert journal(
        project, config, state_root, "worker-1", "result", {"result": "X3"}
    ).returncode == 0
    assert journal(
        project, config, state_root, "worker-1", "note", {"note": "N4"}
    ).returncode == 0
    attempt = run_tool(
        TEAM, project, config, "attempt", "--session", "worker-1",
        "--command", "python3 -c \"print('ATTEMPT-SENTINEL')\"",
        state_root=state_root,
    )
    assert attempt.returncode == 0, attempt.stderr
    assert send(
        project, config, state_root, "worker-1", "mentor", "ask", "STUCK-SENTINEL"
    ).returncode == 0
    assert context(project, config, state_root).returncode == 0

    result = context(project, config, state_root)
    assert result.returncode == 0, result.stderr
    trail = payload_section(result.stdout, "TRAIL")
    assert trail.index("R1") < trail.index("P2") < trail.index("X3") < trail.index("N4")
    assert "ATTEMPT-SENTINEL" not in trail
    assert "STUCK-SENTINEL" not in trail


def test_trail_is_a_fixed_line_when_the_worker_has_no_entries(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_mentor(project, config, state_root).returncode == 0
    assert bind(project, config, state_root, "mentor", "mentor-1").returncode == 0

    result = context(project, config, state_root)
    assert result.returncode == 0, result.stderr
    assert payload_section(result.stdout, "TRAIL") == team.NO_TRAIL


# --- feature scenario 5: FAILURE reproduces the evidence verbatim -----------


def test_failure_prefers_the_task_json_value(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_mentor(
        project, config, state_root, "m1",
        "--failure", "AssertionError: expected 3 got 2",
    ).returncode == 0
    assert bind(project, config, state_root, "mentor", "mentor-1").returncode == 0

    result = context(project, config, state_root)
    assert result.returncode == 0, result.stderr
    assert payload_section(result.stdout, "FAILURE") == "AssertionError: expected 3 got 2"


@pytest.mark.parametrize(
    "field,evidence",
    [
        ("failure", "AssertionError: expected 3 got 2"),
        ("evidence", "Traceback line 42 -> boom; retry exhausted"),
    ],
)
def test_failure_falls_back_to_the_latest_stuck_entry(tmp_path, field, evidence):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_mentor(project, config, state_root).returncode == 0
    assert bind(project, config, state_root, "worker", "worker-1").returncode == 0
    assert bind(project, config, state_root, "mentor", "mentor-1").returncode == 0
    assert journal(
        project, config, state_root, "worker-1", "stuck", {field: evidence}
    ).returncode == 0

    result = context(project, config, state_root)
    assert result.returncode == 0, result.stderr
    assert payload_section(result.stdout, "FAILURE") == evidence


def test_failure_falls_back_to_the_referenced_attempt_output(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_mentor(project, config, state_root).returncode == 0
    assert bind(project, config, state_root, "worker", "worker-1").returncode == 0
    assert bind(project, config, state_root, "mentor", "mentor-1").returncode == 0
    attempt = run_tool(
        TEAM, project, config, "attempt", "--session", "worker-1",
        "--command", "python3 -c \"print('attempt failure evidence')\"",
        state_root=state_root,
    )
    assert attempt.returncode == 0, attempt.stderr
    attached = run_tool(
        TEAM, project, config, "journal", "--session", "worker-1", "--kind", "stuck",
        "--entry", "{}", "--attempt", "1", state_root=state_root,
    )
    assert attached.returncode == 0, attached.stderr

    result = context(project, config, state_root)
    assert result.returncode == 0, result.stderr
    assert "attempt failure evidence" in payload_section(result.stdout, "FAILURE")


def test_empty_ask_and_failure_render_fixed_lines(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_mentor(project, config, state_root).returncode == 0
    assert bind(project, config, state_root, "mentor", "mentor-1").returncode == 0

    result = context(project, config, state_root)
    assert result.returncode == 0, result.stderr
    assert payload_section(result.stdout, "ASK") == team.NO_ASK
    assert payload_section(result.stdout, "FAILURE") == team.NO_FAILURE


def test_ask_falls_back_to_the_latest_stuck_message(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_mentor(project, config, state_root).returncode == 0
    assert bind(project, config, state_root, "worker", "worker-1").returncode == 0
    assert bind(project, config, state_root, "mentor", "mentor-1").returncode == 0
    assert send(
        project, config, state_root, "worker-1", "mentor", "ask", "fallback ask"
    ).returncode == 0

    result = context(project, config, state_root)
    assert result.returncode == 0, result.stderr
    assert payload_section(result.stdout, "ASK") == "fallback ask"


# --- feature scenario 6: assembled without a model call ---------------------


def test_mentor_payload_assembly_makes_no_network_calls(tmp_path):
    state = tmp_path / "state"
    chunk_name = "01-mentor"
    date_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    team.create_chunk_dirs(state, "m1", chunk_name, date_str)
    with mock.patch(
        "urllib.request.urlopen", side_effect=AssertionError("network call")
    ) as urlopen, mock.patch(
        "socket.socket", side_effect=AssertionError("socket call")
    ) as sock:
        lines = team.mentor_payload_lines(
            state, "m1", chunk_name, mentor_task_doc(), date_str
        )
    assert lines[0] == team.MENTOR_SYSTEM_PROMPT
    urlopen.assert_not_called()
    sock.assert_not_called()


# --- feature scenario 7: stable across calls, advice excluded ---------------


def test_payload_is_stable_across_calls(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_mentor(
        project, config, state_root, "m1", "--goal", "g", "--rules", "r"
    ).returncode == 0
    assert bind(project, config, state_root, "mentor", "mentor-1").returncode == 0

    first = context(project, config, state_root)
    second = context(project, config, state_root)
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first.stdout == second.stdout


def test_advice_entries_are_excluded_from_the_trail(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_mentor(project, config, state_root).returncode == 0
    assert bind(project, config, state_root, "mentor", "mentor-1").returncode == 0
    assert context(project, config, state_root).returncode == 0

    result = context(project, config, state_root)
    assert result.returncode == 0, result.stderr
    assert "advice" not in payload_section(result.stdout, "TRAIL")


# --- open records the mentor fields -----------------------------------------


def test_open_records_mentor_fields_from_flags(tmp_path):
    project, config = project_config(tmp_path)
    assert open_mentor(
        project, config, project / "state", "m1",
        "--goal", "the goal", "--rules", "the rules",
        "--ask", "the ask", "--failure", "the failure",
    ).returncode == 0
    doc = json.loads((task_dir(project) / "task.json").read_text())
    assert doc["mentor"] == {
        "goal": "the goal",
        "rules": "the rules",
        "ask": "the ask",
        "failure": "the failure",
    }


def test_open_parses_mentor_fields_from_the_brief(tmp_path):
    project, config = project_config(tmp_path)
    brief = tmp_path / "brief.md"
    brief.write_text(
        "## GOAL\nthe brief goal\n"
        "## RULES\nthe brief rules\n"
        "## ASK\nthe brief ask\n"
        "## FAILURE\nthe brief failure\n"
    )
    assert open_mentor(
        project, config, project / "state", "m1", "--brief", str(brief)
    ).returncode == 0
    doc = json.loads((task_dir(project) / "task.json").read_text())
    assert doc["mentor"] == {
        "goal": "the brief goal",
        "rules": "the brief rules",
        "ask": "the brief ask",
        "failure": "the brief failure",
    }


# --- migration: delta keeps the journal delivery ----------------------------


def test_mentor_delta_still_delivers_journal_entries(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    assert open_mentor(project, config, state_root).returncode == 0
    assert bind(project, config, state_root, "worker", "worker-1").returncode == 0
    assert bind(project, config, state_root, "mentor", "mentor-1").returncode == 0
    assert context(project, config, state_root).returncode == 0
    assert journal(
        project, config, state_root, "worker-1", "plan",
        {"plan": "mentor-delta-sentinel"},
    ).returncode == 0

    delta = context(project, config, state_root, "mentor-1", "--delta")
    assert delta.returncode == 0, delta.stderr
    assert "mode delta" in delta.stdout
    assert "mentor-delta-sentinel" in delta.stdout


def test_coder_payload_is_not_hijacked_by_the_mentor_branch(tmp_path):
    project, config = project_config(tmp_path)
    state_root = project / "state"
    opened = run_tool(
        TEAM, project, config, "open", "c1", "--role", "coder",
        "--goal", "mentor-only", state_root=state_root,
    )
    assert opened.returncode == 0, opened.stderr
    assert bind(project, config, state_root, "worker", "sw", task="c1").returncode == 0

    result = context(project, config, state_root, "sw")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0] == "TASK"
    assert payload_headers(result.stdout) == []


# --- in-process unit tests for the pure assembly helpers --------------------
#
# The CLI suites above spawn ``team.py`` in a subprocess, which coverage cannot
# see. These tests import the module and call the helpers directly, pinning the
# same contract while measuring the assembly code itself.


def journal_entry(seq, kind, **fields):
    return {"seq": seq, "kind": kind, "at": "2020-01-01T00:00:00Z", **fields}


def test_trail_lines_render_worker_entries_in_seq_order():
    entries = [
        journal_entry(3, "result", result="third"),
        journal_entry(1, "plan", plan="first"),
        journal_entry(2, "readback", readback="second"),
    ]
    assert team.trail_lines(entries) == [
        'plan: {"plan": "first"}',
        'readback: {"readback": "second"}',
        'result: {"result": "third"}',
    ]


def test_trail_lines_exclude_tool_entries_and_fall_back_when_empty():
    tool_entries = [
        journal_entry(seq, kind)
        for seq, kind in enumerate(["open", "attempt", "stuck", "advice", "done"], 1)
    ]
    assert team.trail_lines(tool_entries) == [team.NO_TRAIL]
    assert team.trail_lines([]) == [team.NO_TRAIL]


def test_trail_lines_render_a_bare_kind_when_the_payload_is_empty():
    assert team.trail_lines([journal_entry(1, "note")]) == ["note"]


def test_ask_text_prefers_the_latest_stuck_message():
    entries = [
        journal_entry(1, "stuck", message="older ask"),
        journal_entry(4, "stuck", message="newer ask"),
        journal_entry(7, "plan", plan="ignored"),
    ]
    assert team.ask_text(entries) == "newer ask"


def test_ask_text_falls_back_when_there_is_no_usable_stuck_message():
    assert team.ask_text([]) == team.NO_ASK
    assert team.ask_text([journal_entry(1, "stuck", message="")]) == team.NO_ASK


def test_failure_text_is_the_fixed_line_without_stuck_evidence(tmp_path):
    state = tmp_path / "state"
    assert team.failure_text(state, "m1", "01-mentor", "2020-01-01", []) == team.NO_FAILURE
    assert (
        team.failure_text(
            state, "m1", "01-mentor", "2020-01-01", [journal_entry(1, "stuck")]
        )
        == team.NO_FAILURE
    )


def test_failure_text_prefers_recorded_evidence_over_the_attempt_output(tmp_path):
    state = tmp_path / "state"
    chunk, date = "01-mentor", "2020-01-01"
    team.create_chunk_dirs(state, "m1", chunk, date)
    team.attempt_output_path(state, "m1", chunk, 1, date).write_text("attempt output")
    entries = [journal_entry(1, "stuck", failure="recorded", refs=["attempt-01.txt"])]
    assert team.failure_text(state, "m1", chunk, date, entries) == "recorded"


def test_failure_text_reads_the_referenced_attempt_output(tmp_path):
    state = tmp_path / "state"
    chunk, date = "01-mentor", "2020-01-01"
    team.create_chunk_dirs(state, "m1", chunk, date)
    team.attempt_output_path(state, "m1", chunk, 1, date).write_text("boom output")
    entries = [journal_entry(1, "stuck", refs=["attempt-01.txt"])]
    assert team.failure_text(state, "m1", chunk, date, entries) == "boom output"


def test_failure_text_degrades_when_the_reference_is_missing_or_unreadable(tmp_path):
    state = tmp_path / "state"
    chunk, date = "01-mentor", "2020-01-01"
    team.create_chunk_dirs(state, "m1", chunk, date)
    missing = [journal_entry(1, "stuck", refs=["attempt-09.txt"])]
    assert team.failure_text(state, "m1", chunk, date, missing) == team.NO_FAILURE
    team.attempt_output_path(state, "m1", chunk, 1, date).write_bytes(b"\xff\xfe")
    unreadable = [journal_entry(2, "stuck", refs=["attempt-01.txt"])]
    assert team.failure_text(state, "m1", chunk, date, unreadable) == team.NO_FAILURE


def test_attach_attempt_keeps_the_entry_bookkeeping_and_adds_attempt_facts():
    attempt = {
        "seq": 7,
        "kind": "attempt",
        "at": "attempt-time",
        "attempt": 1,
        "cmd": "pytest",
        "exit": 1,
        "refs": ["attempt-01.txt"],
    }
    entry = {"seq": 9, "kind": "stuck", "at": "entry-time", "message": "why"}
    team.attach_attempt(entry, 1, [attempt])
    assert entry == {
        "seq": 9,
        "kind": "stuck",
        "at": "entry-time",
        "message": "why",
        "attempt": 1,
        "cmd": "pytest",
        "exit": 1,
        "refs": ["attempt-01.txt"],
    }


def test_attach_attempt_refuses_an_unknown_attempt():
    with pytest.raises(team.TeamError, match="attempt artifact not found"):
        team.attach_attempt({}, 9, [])


def test_mentor_payload_lines_join_state_and_journal_sections(tmp_path):
    state = tmp_path / "state"
    chunk, date = "01-mentor", "2020-01-01"
    team.create_chunk_dirs(state, "m1", chunk, date)
    for record in (
        journal_entry(1, "plan", plan="step one"),
        journal_entry(2, "result", result="step two"),
        journal_entry(3, "stuck", message="why does it fail"),
    ):
        team.append_journal(state, "m1", chunk, record, date)

    lines = team.mentor_payload_lines(
        state, "m1", chunk, mentor_task_doc(goal="the goal", rules="the rules"), date
    )
    text = "\n".join(lines)
    assert lines[0] == team.MENTOR_SYSTEM_PROMPT
    assert payload_headers(text) == MENTOR_HEADERS
    assert payload_section(text, "GOAL") == "the goal"
    assert payload_section(text, "RULES") == "the rules"
    assert payload_section(text, "ASK") == "why does it fail"
    assert payload_section(text, "FAILURE") == team.NO_FAILURE
    trail = payload_section(text, "TRAIL")
    assert trail.index("step one") < trail.index("step two")

