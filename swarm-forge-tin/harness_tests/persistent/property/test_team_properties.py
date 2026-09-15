"""Property tests for the team tool's task-path and journal storage invariants."""

import datetime
import json
import shutil
import types
from pathlib import Path

import pytest
import team
import wiring
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

VALID_SEGMENT = st.from_regex(r"[A-Za-z0-9][A-Za-z0-9._-]{0,7}", fullmatch=True)
VALID_TASK = st.lists(VALID_SEGMENT, min_size=1, max_size=3).map("/".join)
BAD_SEGMENT = st.sampled_from(["", ".", "..", "-lead", "_lead", ".lead", "sp ace"])
LOWER_TEXT = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Nd", "P", "Zs")),
    min_size=1,
    max_size=20,
)
SETTINGS = settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


def write_project(tmp_path, **fields):
    project = tmp_path / "project"
    project.mkdir(parents=True, exist_ok=True)
    config = project / "harness.json"
    config.write_text(json.dumps({"version": 1, "workspace_root": ".", **fields}))
    return project, config


@SETTINGS
@given(task=VALID_TASK)
def test_valid_task_paths_are_accepted_and_confined(tmp_path, task):
    assert team.task_problem(task) is None
    state = tmp_path / "state"
    assert team._task_dir(state, task).is_relative_to(state / "tasks")


@SETTINGS
@given(task=VALID_TASK, bad=BAD_SEGMENT)
def test_bad_segments_are_rejected(tmp_path, task, bad):
    assert team.task_problem(f"{task}/{bad}") is not None


DATE = st.dates(
    min_value=datetime.date(2000, 1, 1), max_value=datetime.date(2035, 12, 31)
)
DATED_TASK = st.lists(
    st.tuples(DATE, st.booleans()), unique_by=lambda item: item[0], max_size=6
)


@SETTINGS
@given(entries=DATED_TASK, task=VALID_TASK)
def test_find_task_date_returns_the_newest_live_folder(tmp_path, entries, task):
    state = tmp_path / "state"
    shutil.rmtree(state, ignore_errors=True)
    tasks_root = state / "tasks"
    # A plain file under tasks/ must be skipped, not crash the walk.
    tasks_root.mkdir(parents=True)
    (tasks_root / "stray").write_text("")
    expected = None
    for date, holds_task in entries:
        name = date.isoformat()
        folder = tasks_root / name / task
        folder.mkdir(parents=True)
        if holds_task:
            (folder / "task.json").write_text("{}")
            if expected is None or name > expected:
                expected = name
    assert team.find_task_date(state, task) == expected


@SETTINGS
@given(task=VALID_TASK)
def test_find_task_date_is_none_without_a_live_folder(tmp_path, task):
    state = tmp_path / "state"
    shutil.rmtree(state, ignore_errors=True)
    assert team.find_task_date(state, task) is None
    (state / "tasks" / "2020-01-01" / task).mkdir(parents=True)
    assert team.find_task_date(state, task) is None


# A valid JSON document can never be followed by a stray `{`, so the suffix
# guarantees the record is malformed regardless of the generated prefix.
MALFORMED_JSON = st.text(min_size=1, max_size=40).map(lambda text: text + "{")


def _write_task_record(state, task, date, text):
    path = state / "tasks" / date / task / "task.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@SETTINGS
@given(task=VALID_TASK, text=MALFORMED_JSON)
def test_load_task_json_fails_closed_on_a_corrupt_record(tmp_path, task, text):
    state = tmp_path / "state"
    _write_task_record(state, task, "2020-01-01", text)
    with pytest.raises(team.TeamError) as refusal:
        team.load_task_json(state, task, "2020-01-01")
    assert "corrupt" in str(refusal.value)


@SETTINGS
@given(task=VALID_TASK)
def test_load_task_json_refuses_a_missing_record(tmp_path, task):
    with pytest.raises(team.TeamError) as refusal:
        team.load_task_json(tmp_path / "state", task, "2020-01-01")
    assert "does not exist" in str(refusal.value)


@SETTINGS
@given(
    entries=st.lists(
        st.dictionaries(st.text(max_size=4), st.integers()), min_size=1, max_size=5
    )
)
def test_journal_appends_stay_ordered_and_replayable(tmp_path, entries):
    state = tmp_path / "state"
    shutil.rmtree(state, ignore_errors=True)
    task, chunk = "c1", "01-coder"
    for payload in entries:
        seq = team.next_journal_seq(state, task, chunk)
        team.append_journal(
            state, task, chunk, {"seq": seq, "kind": "note", "payload": payload}
        )
    journal = team.read_journal(state, task, chunk)
    assert [entry["seq"] for entry in journal] == list(range(1, len(entries) + 1))
    assert [entry["payload"] for entry in journal] == entries


@SETTINGS
@given(task=LOWER_TEXT, done=LOWER_TEXT, inputs=st.lists(LOWER_TEXT, max_size=3))
def test_coder_payload_keeps_the_fixed_sections_in_order(
    tmp_path, monkeypatch, task, done, inputs
):
    project, config = write_project(tmp_path)
    monkeypatch.setenv("SWARM_CONFIG", str(config))
    wiring.clear_cache()
    task_doc = {
        "task": task,
        "definition_of_done": done,
        "inputs": inputs,
        "role": "coder",
    }
    lines = team.coder_payload_lines(
        project, project / "state", task, "01-coder", task_doc, "2020-01-01"
    )
    headers = [line for line in lines if line in team.CODER_SECTION_HEADERS]
    assert headers == list(team.CODER_SECTION_HEADERS)


WORKER_ENTRY = st.tuples(
    st.integers(min_value=1, max_value=10_000),
    st.sampled_from(list(team.WORKER_KINDS)),
)
TOOL_ENTRY = st.tuples(
    st.integers(min_value=1, max_value=10_000),
    st.sampled_from([kind for kind in team.ALL_KINDS if kind not in team.WORKER_KINDS]),
)


@SETTINGS
@given(entries=st.lists(WORKER_ENTRY, min_size=1, max_size=6, unique_by=lambda item: item[0]))
def test_trail_lines_list_worker_entries_in_seq_order(entries):
    records = [
        {"seq": seq, "kind": kind, "at": "t", "tag": f"tag-{seq}"}
        for seq, kind in entries
    ]
    lines = team.trail_lines(records)
    assert lines == [
        f'{kind}: {{"tag": "tag-{seq}"}}' for seq, kind in sorted(entries)
    ]


@SETTINGS
@given(entries=st.lists(TOOL_ENTRY, max_size=6))
def test_trail_lines_ignore_tool_authored_entries(entries):
    records = [{"seq": seq, "kind": kind, "at": "t"} for seq, kind in entries]
    assert team.trail_lines(records) == [team.NO_TRAIL]


ROOT_KINDS = ("harness", "project", "other")


def _resolved(config_path, pack_root, entries):
    return types.SimpleNamespace(
        config_path=config_path,
        pack_root=pack_root,
        persistent_tests=tuple(
            {"root": Path(root), "kind": kind} for root, kind in entries
        ),
    )


def _expected_root(entries, preferred):
    for kind in preferred:
        for root, entry_kind in entries:
            if entry_kind == kind:
                return Path(root)
    return Path(entries[0][0])


@SETTINGS
@given(
    kinds=st.lists(st.sampled_from(ROOT_KINDS), min_size=1, max_size=4),
    self_hosted=st.booleans(),
)
def test_persistent_test_root_picks_the_configured_kind_without_disk(
    tmp_path, kinds, self_hosted
):
    pack = tmp_path / "pack"
    config_dir = pack if self_hosted else tmp_path / "wired"
    entries = [
        (str(tmp_path / "absent" / f"root{index}"), kind)
        for index, kind in enumerate(kinds)
    ]
    resolved = _resolved(config_dir / "harness.json", pack, entries)
    preferred = ("harness", "project") if self_hosted else ("project", "harness")

    chosen = team.persistent_test_root(resolved)

    assert chosen == _expected_root(entries, preferred)
    assert not chosen.exists()


@SETTINGS
@given(goal=LOWER_TEXT, rules=LOWER_TEXT, ask=LOWER_TEXT, failure=LOWER_TEXT)
def test_mentor_payload_keeps_the_fixed_sections_in_order(
    tmp_path, goal, rules, ask, failure
):
    state = tmp_path / "state"
    task, chunk, date = "m1", "01-mentor", "2020-01-01"
    team.create_chunk_dirs(state, task, chunk, date)
    task_doc = {
        "task": task,
        "mentor": {"goal": goal, "rules": rules, "ask": ask, "failure": failure},
    }
    lines = team.mentor_payload_lines(state, task, chunk, task_doc, date)
    assert lines[0] == team.MENTOR_SYSTEM_PROMPT
    headers = [line for line in lines if line in team.MENTOR_SECTION_HEADERS]
    assert headers == list(team.MENTOR_SECTION_HEADERS)


SEAT = st.sampled_from(["worker", "mentor"])
SESSION = st.one_of(st.none(), st.from_regex(r"[a-z][a-z0-9-]{0,6}", fullmatch=True))


@SETTINGS
@given(
    seats=st.dictionaries(
        SEAT,
        st.fixed_dictionaries({"session": SESSION}),
        min_size=1,
        max_size=2,
    ),
)
def test_ready_entries_lists_each_seat_once(seats):
    rows = team.ready_entries([{"task": "c1", "roles": seats}])
    expected = [
        ("c1", seat, "queued" if info["session"] else "SPAWN_PENDING")
        for seat, info in seats.items()
    ]
    assert sorted(rows) == sorted(expected)


ATTEMPT_FIELDS = st.dictionaries(
    st.sampled_from(["cmd", "exit", "cwd", "timeout", "refs"]),
    st.one_of(st.integers(), st.text(max_size=5), st.booleans()),
    max_size=3,
)
ENTRY_FIELDS = st.dictionaries(
    st.sampled_from(["seq", "kind", "at", "reading", "note"]),
    st.one_of(st.integers(), st.text(max_size=5)),
    max_size=3,
)


@SETTINGS
@given(
    entry=ENTRY_FIELDS,
    attempt=st.integers(min_value=1, max_value=20),
    fields=ATTEMPT_FIELDS,
)
def test_attach_attempt_merges_fields_and_keeps_entry_bookkeeping(entry, attempt, fields):
    record = {"seq": 99, "kind": "attempt", "at": "t", "attempt": attempt, **fields}
    merged = dict(entry)
    team.attach_attempt(merged, attempt, [record])
    for key, value in fields.items():
        assert merged[key] == value
    for key in ("seq", "kind", "at"):
        if key in entry:
            assert merged[key] == entry[key]

    again = dict(entry)
    team.attach_attempt(again, attempt, [record])
    assert again == merged

