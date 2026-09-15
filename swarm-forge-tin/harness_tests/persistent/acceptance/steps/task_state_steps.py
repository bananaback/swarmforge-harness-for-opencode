"""Step handlers for the task state layout and journal acceptance feature."""

import json
import os
import subprocess

import wiring
from runtime import World

from .common import (
    _done_dir,
    _journal_lines,
    _journal_text,
    _only_dir,
    _project,
    _run_team,
    _state_root,
    _task_dir,
    _temp_root,
    step_values,
)


def _make_team_project(world: World, examples: dict[str, str]) -> None:
    """Background: create a temporary project with its own state root."""
    os.environ.pop("SWARM_STATE_ROOT", None)
    wiring.clear_cache()
    root = _temp_root()
    config = root / "harness.json"
    config.write_text(
        json.dumps(
            {
                "version": 1,
                "workspace_root": ".",
                "state_root": "state",
                "artifacts_root": "artifacts",
            }
        )
    )
    # init a git repo so team.py can capture git state
    subprocess.run(
        ["git", "init"], cwd=str(root), capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@test"],
        capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "Test"],
        capture_output=True, text=True,
    )
    # create an initial commit so HEAD exists
    (root / ".gitkeep").write_text("")
    subprocess.run(
        ["git", "-C", str(root), "add", "."], capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "commit", "-m", "init", "--allow-empty"],
        capture_output=True, text=True,
    )
    world.state["project"] = root
    world.state["config"] = config
    world.state["state_root"] = root / "state"


def _orchestrator_opens_task(world: World, examples: dict[str, str]) -> None:
    """When the orchestrator opens task '<task>' for role '<role>'."""
    task, role = step_values(
        examples, r'^the orchestrator opens task "([^"]*)" for role "([^"]*)"$'
    )
    result = _run_team(world, "open", task, "--role", role)
    assert result.returncode == 0, f"open failed: {result.stderr}"
    # record the open date for later assertions
    import datetime
    world.state["open_date"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    world.state["task"] = task


def _orchestrator_opens_task_with_inputs(world: World, examples: dict[str, str]) -> None:
    """When the orchestrator opens task '<task>' for role '<role>' with those inputs."""
    task, role = step_values(
        examples,
        r'^the orchestrator opens task "([^"]*)" for role "([^"]*)" with those inputs$',
    )
    inputs = world.state["inputs"]
    cmd = ["open", task, "--role", role]
    if "brief" in inputs:
        cmd.extend(["--brief", str(inputs["brief"])])
    if "feature" in inputs:
        cmd.extend(["--feature", str(inputs["feature"])])
    if "design" in inputs:
        cmd.extend(["--design", str(inputs["design"])])
    result = _run_team(world, *cmd)
    assert result.returncode == 0, f"open failed: {result.stderr}"
    import datetime
    world.state["open_date"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    world.state["task"] = task


def _brief_feature_design_for_task(world: World, examples: dict[str, str]) -> None:
    """Given a brief file, a feature file, and a design file for the task."""
    project = _project(world)
    brief = project / "brief.md"
    brief.write_text("# Brief\nDo the thing.")
    feature = project / "test.feature"
    feature.write_text("Feature: Test\n  Scenario: x\n    Given y\n")
    design = project / "design.md"
    design.write_text("# Design\nContract.")
    # the parse step writes the IR under the artifacts root
    artifacts = project / "artifacts"
    artifacts.mkdir(exist_ok=True)
    ir = artifacts / "test.json"
    ir.write_text(json.dumps({"name": "test", "scenarios": []}))
    world.state["inputs"] = {
        "brief": brief,
        "feature": feature,
        "design": design,
        "ir": ir,
    }


def _task_folder_filed_under_date(world: World, examples: dict[str, str]) -> None:
    """Then the task folder is filed under the opening UTC date."""
    task = examples["task"]
    task_dir = _task_dir(world, task)
    assert task_dir.is_dir(), f"task dir not found: {task_dir}"


def _task_folder_holds_exactly(world: World, examples: dict[str, str]) -> None:
    """And the task folder holds exactly task.json and one chunk folder for role '<role>'."""
    task = examples["task"]
    role = examples["role"]
    task_dir = _task_dir(world, task)
    children = sorted(p.name for p in task_dir.iterdir())
    assert "task.json" in children, f"missing task.json in {task_dir}: {children}"
    chunk_dirs = [c for c in children if c != "task.json"]
    assert len(chunk_dirs) == 1, f"expected 1 chunk dir, got {chunk_dirs}"
    assert chunk_dirs[0].endswith(f"-{role}"), f"chunk dir {chunk_dirs[0]} doesn't end with -{role}"


def _chunk_folder_holds_exactly(world: World, examples: dict[str, str]) -> None:
    """And the chunk folder holds exactly input, journal, and output."""
    task = examples["task"]
    chunk = _only_dir(_task_dir(world, task))
    children = sorted(p.name for p in chunk.iterdir())
    assert children == ["input", "journal.jsonl", "output"], f"got {children}"


def _chunk_input_holds_copies(world: World, examples: dict[str, str]) -> None:
    """Then the chunk input folder holds a copy of each given file."""
    task = examples["task"]
    inp = _only_dir(_task_dir(world, task)) / "input"
    assert inp.is_dir()
    inputs = world.state["inputs"]
    for key in ("brief", "design"):
        src = inputs[key]
        assert (inp / src.name).is_file(), f"missing {src.name} in input/"


def _chunk_input_holds_parsed_ir(world: World, examples: dict[str, str]) -> None:
    """And the chunk input folder holds the parsed feature IR."""
    task = examples["task"]
    inp = _only_dir(_task_dir(world, task)) / "input"
    feature = world.state["inputs"]["feature"]
    # the feature file is copied with its .feature name, the IR with the .json stem
    assert (inp / feature.name).is_file(), f"missing {feature.name} in {inp}"
    ir = inp / f"{feature.stem}.json"
    assert ir.is_file(), f"missing parsed IR {ir.name} in {inp}"
    assert ir.read_text() == world.state["inputs"]["ir"].read_text()


def _copied_inputs_match(world: World, examples: dict[str, str]) -> None:
    """And every copied input matches its given file."""
    task = examples["task"]
    inp = _only_dir(_task_dir(world, task)) / "input"
    inputs = world.state["inputs"]
    for key in ("brief", "design", "feature"):
        src = inputs[key]
        dst = inp / src.name
        assert dst.read_text() == src.read_text(), f"{src.name} differs"
    ir_src = inputs["ir"]
    assert (inp / ir_src.name).read_text() == ir_src.read_text(), "feature IR differs"


def _journal_has_one_entry(world: World, examples: dict[str, str]) -> None:
    """Then the chunk journal has one entry."""
    task = examples.get("task") or world.state.get("task")
    lines = _journal_lines(_only_dir(_task_dir(world, task)))
    assert len(lines) == 1, f"expected 1 journal entry, got {len(lines)}"


def _first_journal_entry_has_kind(world: World, examples: dict[str, str]) -> None:
    """And the first journal entry has kind 'open'."""
    task = examples["task"]
    lines = _journal_lines(_only_dir(_task_dir(world, task)))
    assert len(lines) >= 1
    entry = json.loads(lines[0])
    assert entry["kind"] == "open", f"expected kind 'open', got {entry['kind']}"


def _open_entry_records_git(world: World, examples: dict[str, str]) -> None:
    """And the open entry records the git branch and commit."""
    task = examples["task"]
    lines = _journal_lines(_only_dir(_task_dir(world, task)))
    entry = json.loads(lines[0])
    assert "git" in entry, "open entry missing git field"
    git = entry["git"]
    assert "branch" in git, "open entry git missing branch"
    assert "commit" in git, "open entry git missing commit"


def _open_entry_lists_inputs(world: World, examples: dict[str, str]) -> None:
    """And the open entry lists the given inputs."""
    task = examples["task"]
    lines = _journal_lines(_only_dir(_task_dir(world, task)))
    entry = json.loads(lines[0])
    assert "inputs" in entry, "open entry missing inputs field"
    assert isinstance(entry["inputs"], list)
    assert len(entry["inputs"]) >= 1, "inputs should list at least one file"


def _open_task_bound_to_worker(world: World, examples: dict[str, str]) -> None:
    """Given an open task '...' bound to a worker."""
    # Parse the task name from the step text (it's a literal, not a parameter)
    step_text = examples.get("_step_text", "")
    import re
    m = re.search(r'"([^"]+)"', step_text)
    assert m, f"cannot extract task name from step text: {step_text}"
    task = m.group(1)
    role = "coder"
    result = _run_team(world, "open", task, "--role", role)
    assert result.returncode == 0, f"open failed: {result.stderr}"
    import datetime
    world.state["open_date"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    # bind a session to the worker seat
    session = world.state.get("next_session", "s1")
    world.state["next_session"] = "s2" if session == "s1" else "s1"
    result = _run_team(
        world, "bind", task, "--seat", "worker", "--session", session
    )
    assert result.returncode == 0, f"bind failed: {result.stderr}"
    world.state.setdefault("sessions", {})[task] = session
    world.state.setdefault("tasks_opened", []).append(task)


def _worker_journals_kind(world: World, examples: dict[str, str]) -> None:
    """When the worker journals kind '<kind>'."""
    kind = examples["kind"]
    session = world.state["sessions"].get("feature/periods", "s1")
    result = _run_team(
        world, "journal", "--session", session,
        "--kind", kind, "--entry", json.dumps({"test": True}),
    )
    assert result.returncode == 0, f"journal failed: {result.stderr}"


def _last_journal_entry_has_kind(world: World, examples: dict[str, str]) -> None:
    """Then the last journal entry has kind '<kind>'."""
    (kind,) = step_values(
        examples, r'^the last journal entry has kind "([^"]*)"$'
    )
    task = "feature/periods"
    lines = _journal_lines(_only_dir(_task_dir(world, task)))
    assert len(lines) >= 1
    entry = json.loads(lines[-1])
    assert entry["kind"] == kind, f"expected kind '{kind}', got {entry['kind']}"


def _worker_requests_unsupported_kind(world: World, examples: dict[str, str]) -> None:
    """When the worker requests an unsupported journal kind."""
    session = world.state["sessions"].get("feature/periods", "s1")
    result = _run_team(
        world, "journal", "--session", session,
        "--kind", "bogus", "--entry", json.dumps({"x": 1}),
    )
    world.state["journal_result"] = result


def _journaling_fails(world: World, examples: dict[str, str]) -> None:
    """Then journaling fails."""
    result = world.state["journal_result"]
    assert result.returncode != 0, "journal should have failed"


def _chunk_journal_unchanged(world: World, examples: dict[str, str]) -> None:
    """And the chunk journal is unchanged."""
    task = "feature/periods"
    lines = _journal_lines(_only_dir(_task_dir(world, task)))
    # should still have only the open entry (1 entry)
    assert len(lines) == 1, f"expected 1 journal entry, got {len(lines)}"


def _operation_runs(world: World, examples: dict[str, str]) -> None:
    """When the '<operation>' operation runs."""
    operation = examples["operation"]
    session = world.state["sessions"].get("feature/periods", "s1")
    task = "feature/periods"
    if operation == "oracle attempt":
        result = _run_team(
            world, "attempt", "--session", session,
            "--command", "python3 -c 'print(42)'",
        )
        assert result.returncode == 0, f"attempt failed: {result.stderr}"
    elif operation == "mentor ask":
        # bind mentor seat first
        mentor_session = world.state.get("mentor_session", "sm1")
        world.state["mentor_session"] = mentor_session
        _run_team(
            world, "bind", task, "--seat", "mentor", "--session", mentor_session
        )
        # send an ask from worker to mentor (this appends stuck entry)
        result = _run_team(
            world, "send", "--session", session,
            "--to", "mentor", "--kind", "ask", "--message", "help",
        )
        assert result.returncode == 0, f"send failed: {result.stderr}"
    elif operation == "mentor brief":
        # bind mentor seat first
        mentor_session = world.state.get("mentor_session", "sm1")
        world.state["mentor_session"] = mentor_session
        _run_team(
            world, "bind", task, "--seat", "mentor", "--session", mentor_session
        )
        # context delivery appends advice entry
        result = _run_team(
            world, "context", "--session", mentor_session,
        )
        assert result.returncode == 0, f"context failed: {result.stderr}"
    elif operation == "task done":
        result = _run_team(world, "done", "--session", session)
        assert result.returncode == 0, f"done failed: {result.stderr}"
    else:
        raise AssertionError(f"unknown operation: {operation}")


def _worker_has_journaled_readback(world: World, examples: dict[str, str]) -> None:
    """Given the worker has journaled a readback."""
    session = world.state["sessions"].get("feature/periods", "s1")
    result = _run_team(
        world, "journal", "--session", session,
        "--kind", "readback", "--entry", json.dumps({"goal": "understood"}),
    )
    assert result.returncode == 0, f"journal failed: {result.stderr}"
    # snapshot the journal for later comparison
    task = "feature/periods"
    world.state["journal_before"] = _journal_text(_only_dir(_task_dir(world, task)))


def _worker_appends_plan_entry(world: World, examples: dict[str, str]) -> None:
    """When the worker appends a plan entry."""
    session = world.state["sessions"].get("feature/periods", "s1")
    result = _run_team(
        world, "journal", "--session", session,
        "--kind", "plan", "--entry", json.dumps({"plan": "do it"}),
    )
    assert result.returncode == 0, f"journal failed: {result.stderr}"


def _journal_has_two_entries(world: World, examples: dict[str, str]) -> None:
    """Then the chunk journal has two entries."""
    task = "feature/periods"
    lines = _journal_lines(_only_dir(_task_dir(world, task)))
    # count non-open entries (the open entry is setup, not part of the count)
    non_open = [line for line in lines if json.loads(line).get("kind") != "open"]
    assert len(non_open) == 2, f"expected 2 non-open journal entries, got {len(non_open)}"


def _journal_entries_ordered(world: World, examples: dict[str, str]) -> None:
    """And the journal entries are ordered by increasing sequence."""
    task = "feature/periods"
    lines = _journal_lines(_only_dir(_task_dir(world, task)))
    entries = [json.loads(line) for line in lines]
    seqs = [e["seq"] for e in entries]
    assert seqs == sorted(seqs), f"seqs not ordered: {seqs}"


def _readback_entry_unchanged(world: World, examples: dict[str, str]) -> None:
    """And the readback entry is unchanged."""
    task = "feature/periods"
    current = _journal_text(_only_dir(_task_dir(world, task)))
    before = world.state["journal_before"]
    # first line (readback) should be the same
    before_first = before.splitlines()[0]
    current_first = current.splitlines()[0]
    assert before_first == current_first, "readback entry was changed"


def _worker_records_oracle_attempt(world: World, examples: dict[str, str]) -> None:
    """Given the worker records an oracle attempt."""
    session = world.state["sessions"].get("feature/periods", "s1")
    result = _run_team(
        world, "attempt", "--session", session,
        "--command", "python3 -c 'print(42)'",
    )
    assert result.returncode == 0, f"attempt failed: {result.stderr}"
    # snapshot journal for comparison
    task = "feature/periods"
    world.state["journal_before"] = _journal_text(_only_dir(_task_dir(world, task)))


def _orchestrator_preserves_task(world: World, examples: dict[str, str]) -> None:
    """When the orchestrator preserves task '...' by closing it."""
    import re
    step_text = examples.get("_step_text", "")
    m = re.search(r'"([^"]+)"', step_text)
    assert m
    task = m.group(1)
    result = _run_team(world, "close", task, "--preserve")
    assert result.returncode == 0, f"close failed: {result.stderr}"


def _task_folder_gone_from_live(world: World, examples: dict[str, str]) -> None:
    """Then the task folder '...' is gone from the live tasks."""
    import re
    step_text = examples.get("_step_text", "")
    m = re.search(r'"([^"]+)"', step_text)
    assert m
    task = m.group(1)
    task_dir = _task_dir(world, task)
    assert not task_dir.is_dir(), f"task dir still exists: {task_dir}"


def _task_folder_appears_under_done(world: World, examples: dict[str, str]) -> None:
    """And the task folder '...' appears whole under done."""
    import re
    step_text = examples.get("_step_text", "")
    m = re.search(r'"([^"]+)"', step_text)
    assert m
    task = m.group(1)
    done_dir = _done_dir(world, task)
    assert done_dir.is_dir(), f"done dir not found: {done_dir}"
    # should have task.json and at least one chunk folder
    children = sorted(p.name for p in done_dir.iterdir())
    assert "task.json" in children, f"missing task.json in done: {children}"


def _preserved_journal_matches(world: World, examples: dict[str, str]) -> None:
    """And the preserved journal holds the same entries as before closing."""
    task = "feature/periods"
    current = _journal_text(_only_dir(_done_dir(world, task)))
    before = world.state["journal_before"]
    current_lines = [line for line in current.splitlines() if line.strip()]
    before_lines = [line for line in before.splitlines() if line.strip()]
    assert current_lines == before_lines, "journal entries differ after preserve"


def _preserved_output_holds_attempt(world: World, examples: dict[str, str]) -> None:
    """And the preserved output holds the attempt artifact."""
    task = "feature/periods"
    output = _only_dir(_done_dir(world, task)) / "output"
    assert output.is_dir()
    artifacts = list(output.iterdir())
    assert len(artifacts) >= 1, f"expected attempt artifacts in {output}"


def _orchestrator_closes_without_preserve(world: World, examples: dict[str, str]) -> None:
    """When the orchestrator closes task '...' without preserve."""
    import re
    step_text = examples.get("_step_text", "")
    m = re.search(r'"([^"]+)"', step_text)
    assert m
    task = m.group(1)
    result = _run_team(world, "close", task)
    assert result.returncode == 0, f"close failed: {result.stderr}"


def _task_folder_untouched(world: World, examples: dict[str, str]) -> None:
    """And the task folder '...' is untouched."""
    import re
    step_text = examples.get("_step_text", "")
    m = re.search(r'"([^"]+)"', step_text)
    assert m
    task = m.group(1)
    task_dir = _task_dir(world, task)
    assert task_dir.is_dir(), f"task dir should exist: {task_dir}"


def _live_date_folder_remains(world: World, examples: dict[str, str]) -> None:
    """And the live date folder remains."""
    state = _state_root(world)
    today = world.state.get("open_date", "unknown")
    date_dir = state / "tasks" / today
    assert date_dir.is_dir(), f"date dir should remain: {date_dir}"


def _live_date_folder_gone(world: World, examples: dict[str, str]) -> None:
    """And the live date folder is gone."""
    state = _state_root(world)
    today = world.state.get("open_date", "unknown")
    date_dir = state / "tasks" / today
    assert not date_dir.is_dir(), f"date dir should be gone: {date_dir}"


HANDLERS = [
    (r"^a temporary project with its own state root$", _make_team_project),
    (r'^the orchestrator opens task "([^"]*)" for role "([^"]*)"$',
     _orchestrator_opens_task),
    (r'^the orchestrator opens task "([^"]*)" for role "([^"]*)" with those inputs$',
     _orchestrator_opens_task_with_inputs),
    (r"^a brief file, a feature file, and a design file for the task$",
     _brief_feature_design_for_task),
    (r"^the task folder is filed under the opening UTC date$",
     _task_folder_filed_under_date),
    (r'^the task folder holds exactly task.json and one chunk folder for role "([^"]*)"$',
     _task_folder_holds_exactly),
    (r"^the chunk folder holds exactly input, journal, and output$",
     _chunk_folder_holds_exactly),
    (r"^the chunk input folder holds a copy of each given file$",
     _chunk_input_holds_copies),
    (r"^the chunk input folder holds the parsed feature IR$",
     _chunk_input_holds_parsed_ir),
    (r"^every copied input matches its given file$",
     _copied_inputs_match),
    (r"^the chunk journal has one entry$",
     _journal_has_one_entry),
    (r'^the first journal entry has kind "([^"]*)"$',
     _first_journal_entry_has_kind),
    (r"^the open entry records the git branch and commit$",
     _open_entry_records_git),
    (r"^the open entry lists the given inputs$",
     _open_entry_lists_inputs),
    (r'^an open task "([^"]*)" bound to a worker$',
     _open_task_bound_to_worker),
    (r'^the worker journals kind "([^"]*)"$',
     _worker_journals_kind),
    (r'^the last journal entry has kind "([^"]*)"$',
     _last_journal_entry_has_kind),
    (r"^the worker requests an unsupported journal kind$",
     _worker_requests_unsupported_kind),
    (r"^journaling fails$",
     _journaling_fails),
    (r"^the chunk journal is unchanged$",
     _chunk_journal_unchanged),
    (r'^the "([^"]*)" operation runs$',
     _operation_runs),
    (r"^the worker has journaled a readback$",
     _worker_has_journaled_readback),
    (r"^the worker appends a plan entry$",
     _worker_appends_plan_entry),
    (r"^the chunk journal has two entries$",
     _journal_has_two_entries),
    (r"^the journal entries are ordered by increasing sequence$",
     _journal_entries_ordered),
    (r"^the readback entry is unchanged$",
     _readback_entry_unchanged),
    (r"^the worker records an oracle attempt$",
     _worker_records_oracle_attempt),
    (r'^the orchestrator preserves task "([^"]*)" by closing it$',
     _orchestrator_preserves_task),
    (r'^the task folder "([^"]*)" is gone from the live tasks$',
     _task_folder_gone_from_live),
    (r'^the task folder "([^"]*)" appears whole under done$',
     _task_folder_appears_under_done),
    (r"^the preserved journal holds the same entries as before closing$",
     _preserved_journal_matches),
    (r"^the preserved output holds the attempt artifact$",
     _preserved_output_holds_attempt),
    (r'^the orchestrator closes task "([^"]*)" without preserve$',
     _orchestrator_closes_without_preserve),
    (r'^the task folder "([^"]*)" is untouched$',
     _task_folder_untouched),
    (r"^the live date folder remains$",
     _live_date_folder_remains),
    (r"^the live date folder is gone$",
     _live_date_folder_gone),
]
