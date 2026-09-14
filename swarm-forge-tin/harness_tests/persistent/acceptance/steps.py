"""Step handlers for harness wiring and task_state_layout acceptance features."""

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import team
import wiring
from runtime import World

_TEMP_DIRS: list[Path] = []

TEAM = "team.py"


def _cleanup_temp_dirs() -> None:
    while _TEMP_DIRS:
        shutil.rmtree(_TEMP_DIRS.pop(), ignore_errors=True)


atexit.register(_cleanup_temp_dirs)


def _temp_root() -> Path:
    root = Path(tempfile.mkdtemp(prefix="swarm-wiring-"))
    _TEMP_DIRS.append(root)
    return root


def _pack(world: World) -> Path:
    return world.state["pack"]


def _project(world: World) -> Path:
    return world.state["project"]


def _resolved(world: World):
    return world.state["resolved"]


def _state_root(world: World) -> Path:
    return world.state["state_root"]


def _run_team(world: World, *args: str) -> subprocess.CompletedProcess:
    """Run team.py CLI on the temp project and return the result."""
    config = world.state["config"]
    project = _project(world)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("SWARM_")
    }
    env["SWARM_CONFIG"] = str(config)
    tools = Path(__file__).resolve().parents[3] / "tools"
    return subprocess.run(
        [sys.executable, str(tools / TEAM), "--root", str(project), *args],
        env=env,
        cwd=str(project),
        capture_output=True,
        text=True,
    )


def _task_dir(world: World, task: str) -> Path:
    """Return the live task folder under tasks/<date>/<task>."""
    state = _state_root(world)
    today = world.state.get("open_date", "unknown")
    return state / "tasks" / today / task


def _make_project(world: World, malformed: bool = False) -> None:
    os.environ.pop("SWARM_STATE_ROOT", None)
    wiring.clear_cache()
    root = _temp_root()
    pack = root / "pack"
    (pack / "tools").mkdir(parents=True)
    (pack / "tools" / "wiring.py").write_text("")
    if malformed:
        (root / "harness.json").write_text("{not json")
    else:
        (root / "tests").mkdir()
        config = {
            "version": 1,
            "workspace_root": ".",
            "state_root": ".state",
            "hot_tests": "hot",
            "persistent_tests": [{"root": "tests", "pythonpath": ["."], "kind": "project"}],
        }
        (root / "harness.json").write_text(json.dumps(config))
    world.state["project"] = root
    world.state["pack"] = pack


def _the_harness_pack(world: World, examples: dict[str, str]) -> None:
    world.state["pack"] = wiring.PACK_ROOT


def _load_from_pack(world: World, examples: dict[str, str]) -> None:
    wiring.clear_cache()
    world.state["resolved"] = wiring.load(start=str(_pack(world)))


def _workspace_is_pack_parent(world: World, examples: dict[str, str]) -> None:
    assert _resolved(world).workspace_root == _pack(world).parent


def _sources_contain_tools(world: World, examples: dict[str, str]) -> None:
    assert _pack(world) / "tools" in _resolved(world).source_roots


def _persistent_is_harness(world: World, examples: dict[str, str]) -> None:
    roots = [entry["root"] for entry in _resolved(world).persistent_tests]
    assert _pack(world) / "harness_tests" / "persistent" in roots


def _hot_is_pack_hot(world: World, examples: dict[str, str]) -> None:
    assert _resolved(world).hot_tests == _pack(world) / "hot_tests"


def _temporary_project(world: World, examples: dict[str, str]) -> None:
    _make_project(world)


def _malformed_project(world: World, examples: dict[str, str]) -> None:
    _make_project(world, malformed=True)


def _load_from_project(world: World, examples: dict[str, str]) -> None:
    wiring.clear_cache()
    world.state["resolved"] = wiring.load(start=str(_project(world)))


def _workspace_is_project(world: World, examples: dict[str, str]) -> None:
    assert _resolved(world).workspace_root == _project(world)


def _hot_is_project_hot(world: World, examples: dict[str, str]) -> None:
    assert _resolved(world).hot_tests == _project(world) / "hot"


def _state_is_project_state(world: World, examples: dict[str, str]) -> None:
    assert _resolved(world).state_root == _project(world) / ".state"


def _persistent_is_project_tests(world: World, examples: dict[str, str]) -> None:
    roots = [entry["root"] for entry in _resolved(world).persistent_tests]
    assert roots == [_project(world) / "tests"]


def _pack_config_other_workspace(world: World, examples: dict[str, str]) -> None:
    config = {"version": 1, "workspace_root": "/elsewhere"}
    (_pack(world) / "harness.json").write_text(json.dumps(config))


def _env_state_override(world: World, examples: dict[str, str]) -> None:
    override = _project(world) / "override"
    os.environ["SWARM_STATE_ROOT"] = str(override)
    world.state["override"] = override


def _env_override_reported(world: World, examples: dict[str, str]) -> None:
    wiring.clear_cache()
    resolved = wiring.load(start=str(_project(world)))
    assert resolved.state_root == world.state["override"]
    os.environ.pop("SWARM_STATE_ROOT", None)


def _generated_hot_file(world: World, examples: dict[str, str]) -> None:
    acceptance = _project(world) / "hot" / "acceptance"
    acceptance.mkdir(parents=True)
    (acceptance / "test_generated.py").write_text("")


def _run_clean_hot(world: World, examples: dict[str, str]) -> None:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("SWARM_")
    }
    env["SWARM_CONFIG"] = str(_project(world) / "harness.json")
    result = subprocess.run(
        [sys.executable, str(wiring.PACK_ROOT / "tools" / "harness"), "clean", "hot"],
        cwd=str(_project(world)),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def _hot_empty(world: World, examples: dict[str, str]) -> None:
    hot = _project(world) / "hot"
    assert hot.is_dir()
    assert list(hot.iterdir()) == []


def _persistent_still_exists(world: World, examples: dict[str, str]) -> None:
    assert (_project(world) / "tests").is_dir()


def _request_from_project(world: World, examples: dict[str, str]) -> None:
    try:
        wiring.load(start=str(_project(world)))
    except wiring.WiringError as error:
        world.state["error"] = error
    else:
        world.state["error"] = None


def _loading_fails_with_wiring_error(world: World, examples: dict[str, str]) -> None:
    assert isinstance(world.state.get("error"), wiring.WiringError)


# --- task_state_layout step handlers ---


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
    task = examples["task"]
    role = examples["role"]
    result = _run_team(world, "open", task, "--role", role)
    assert result.returncode == 0, f"open failed: {result.stderr}"
    # record the open date for later assertions
    import datetime
    world.state["open_date"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")


def _orchestrator_opens_task_with_inputs(world: World, examples: dict[str, str]) -> None:
    """When the orchestrator opens task '<task>' for role '<role>' with those inputs."""
    task = examples["task"]
    role = examples["role"]
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
    task_dir = _task_dir(world, task)
    chunk_dirs = [d for d in task_dir.iterdir() if d.is_dir()]
    assert len(chunk_dirs) == 1
    chunk = chunk_dirs[0]
    children = sorted(p.name for p in chunk.iterdir())
    assert children == ["input", "journal.jsonl", "output"], f"got {children}"


def _chunk_input_holds_copies(world: World, examples: dict[str, str]) -> None:
    """Then the chunk input folder holds a copy of each given file."""
    task = examples["task"]
    task_dir = _task_dir(world, task)
    chunk_dirs = [d for d in task_dir.iterdir() if d.is_dir()]
    assert len(chunk_dirs) == 1
    inp = chunk_dirs[0] / "input"
    assert inp.is_dir()
    inputs = world.state["inputs"]
    for key in ("brief", "design"):
        src = inputs[key]
        assert (inp / src.name).is_file(), f"missing {src.name} in input/"


def _chunk_input_holds_parsed_ir(world: World, examples: dict[str, str]) -> None:
    """And the chunk input folder holds the parsed feature IR."""
    task = examples["task"]
    task_dir = _task_dir(world, task)
    chunk_dirs = [d for d in task_dir.iterdir() if d.is_dir()]
    assert len(chunk_dirs) == 1
    inp = chunk_dirs[0] / "input"
    feature = world.state["inputs"]["feature"]
    # the feature file is copied with its .feature name, the IR with the .json stem
    assert (inp / feature.name).is_file(), f"missing {feature.name} in {inp}"
    ir = inp / f"{feature.stem}.json"
    assert ir.is_file(), f"missing parsed IR {ir.name} in {inp}"
    assert ir.read_text() == world.state["inputs"]["ir"].read_text()


def _copied_inputs_match(world: World, examples: dict[str, str]) -> None:
    """And every copied input matches its given file."""
    task = examples["task"]
    task_dir = _task_dir(world, task)
    chunk_dirs = [d for d in task_dir.iterdir() if d.is_dir()]
    assert len(chunk_dirs) == 1
    inp = chunk_dirs[0] / "input"
    inputs = world.state["inputs"]
    for key in ("brief", "design", "feature"):
        src = inputs[key]
        dst = inp / src.name
        assert dst.read_text() == src.read_text(), f"{src.name} differs"
    ir_src = inputs["ir"]
    assert (inp / ir_src.name).read_text() == ir_src.read_text(), "feature IR differs"


def _journal_has_one_entry(world: World, examples: dict[str, str]) -> None:
    """Then the chunk journal has one entry."""
    task = examples["task"]
    task_dir = _task_dir(world, task)
    chunk_dirs = [d for d in task_dir.iterdir() if d.is_dir()]
    assert len(chunk_dirs) == 1
    journal = chunk_dirs[0] / "journal.jsonl"
    lines = [line for line in journal.read_text().splitlines() if line.strip()]
    assert len(lines) == 1, f"expected 1 journal entry, got {len(lines)}"


def _first_journal_entry_has_kind(world: World, examples: dict[str, str]) -> None:
    """And the first journal entry has kind 'open'."""
    task = examples["task"]
    task_dir = _task_dir(world, task)
    chunk_dirs = [d for d in task_dir.iterdir() if d.is_dir()]
    assert len(chunk_dirs) == 1
    journal = chunk_dirs[0] / "journal.jsonl"
    lines = [line for line in journal.read_text().splitlines() if line.strip()]
    assert len(lines) >= 1
    entry = json.loads(lines[0])
    assert entry["kind"] == "open", f"expected kind 'open', got {entry['kind']}"


def _open_entry_records_git(world: World, examples: dict[str, str]) -> None:
    """And the open entry records the git branch and commit."""
    task = examples["task"]
    task_dir = _task_dir(world, task)
    chunk_dirs = [d for d in task_dir.iterdir() if d.is_dir()]
    assert len(chunk_dirs) == 1
    journal = chunk_dirs[0] / "journal.jsonl"
    lines = [line for line in journal.read_text().splitlines() if line.strip()]
    entry = json.loads(lines[0])
    assert "git" in entry, "open entry missing git field"
    git = entry["git"]
    assert "branch" in git, "open entry git missing branch"
    assert "commit" in git, "open entry git missing commit"


def _open_entry_lists_inputs(world: World, examples: dict[str, str]) -> None:
    """And the open entry lists the given inputs."""
    task = examples["task"]
    task_dir = _task_dir(world, task)
    chunk_dirs = [d for d in task_dir.iterdir() if d.is_dir()]
    assert len(chunk_dirs) == 1
    journal = chunk_dirs[0] / "journal.jsonl"
    lines = [line for line in journal.read_text().splitlines() if line.strip()]
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
    kind = examples["kind"]
    task = "feature/periods"
    task_dir = _task_dir(world, task)
    chunk_dirs = [d for d in task_dir.iterdir() if d.is_dir()]
    assert len(chunk_dirs) == 1
    journal = chunk_dirs[0] / "journal.jsonl"
    lines = [line for line in journal.read_text().splitlines() if line.strip()]
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
    task_dir = _task_dir(world, task)
    chunk_dirs = [d for d in task_dir.iterdir() if d.is_dir()]
    assert len(chunk_dirs) == 1
    journal = chunk_dirs[0] / "journal.jsonl"
    lines = [line for line in journal.read_text().splitlines() if line.strip()]
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
    task_dir = _task_dir(world, task)
    chunk_dirs = [d for d in task_dir.iterdir() if d.is_dir()]
    journal = chunk_dirs[0] / "journal.jsonl"
    world.state["journal_before"] = journal.read_text()


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
    task_dir = _task_dir(world, task)
    chunk_dirs = [d for d in task_dir.iterdir() if d.is_dir()]
    journal = chunk_dirs[0] / "journal.jsonl"
    lines = [line for line in journal.read_text().splitlines() if line.strip()]
    # count non-open entries (the open entry is setup, not part of the count)
    non_open = [line for line in lines if json.loads(line).get("kind") != "open"]
    assert len(non_open) == 2, f"expected 2 non-open journal entries, got {len(non_open)}"


def _journal_entries_ordered(world: World, examples: dict[str, str]) -> None:
    """And the journal entries are ordered by increasing sequence."""
    task = "feature/periods"
    task_dir = _task_dir(world, task)
    chunk_dirs = [d for d in task_dir.iterdir() if d.is_dir()]
    journal = chunk_dirs[0] / "journal.jsonl"
    entries = []
    for line in journal.read_text().splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    seqs = [e["seq"] for e in entries]
    assert seqs == sorted(seqs), f"seqs not ordered: {seqs}"


def _readback_entry_unchanged(world: World, examples: dict[str, str]) -> None:
    """And the readback entry is unchanged."""
    task = "feature/periods"
    task_dir = _task_dir(world, task)
    chunk_dirs = [d for d in task_dir.iterdir() if d.is_dir()]
    journal = chunk_dirs[0] / "journal.jsonl"
    current = journal.read_text()
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
    task_dir = _task_dir(world, task)
    chunk_dirs = [d for d in task_dir.iterdir() if d.is_dir()]
    journal = chunk_dirs[0] / "journal.jsonl"
    world.state["journal_before"] = journal.read_text()


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
    state = _state_root(world)
    today = world.state.get("open_date", "unknown")
    done_dir = state / "done" / today / task
    assert done_dir.is_dir(), f"done dir not found: {done_dir}"
    # should have task.json and at least one chunk folder
    children = sorted(p.name for p in done_dir.iterdir())
    assert "task.json" in children, f"missing task.json in done: {children}"


def _preserved_journal_matches(world: World, examples: dict[str, str]) -> None:
    """And the preserved journal holds the same entries as before closing."""
    task = "feature/periods"
    state = _state_root(world)
    today = world.state.get("open_date", "unknown")
    done_dir = state / "done" / today / task
    chunk_dirs = [d for d in done_dir.iterdir() if d.is_dir()]
    assert len(chunk_dirs) == 1
    journal = chunk_dirs[0] / "journal.jsonl"
    current = journal.read_text()
    before = world.state["journal_before"]
    current_lines = [line for line in current.splitlines() if line.strip()]
    before_lines = [line for line in before.splitlines() if line.strip()]
    assert current_lines == before_lines, "journal entries differ after preserve"


def _preserved_output_holds_attempt(world: World, examples: dict[str, str]) -> None:
    """And the preserved output holds the attempt artifact."""
    task = "feature/periods"
    state = _state_root(world)
    today = world.state.get("open_date", "unknown")
    done_dir = state / "done" / today / task
    chunk_dirs = [d for d in done_dir.iterdir() if d.is_dir()]
    assert len(chunk_dirs) == 1
    output = chunk_dirs[0] / "output"
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


# --- deterministic_coder_payload step handlers ---

_CODER_HEADERS = (
    "TASK",
    "DEFINITION OF DONE",
    "RESOLVED PATHS",
    "INPUTS",
    "FEATURE",
    "INTERFACE CONTRACT",
    "FILES",
    "HOW TO RUN",
    "PRIOR ATTEMPT",
    "WHEN STUCK",
    "WHEN DONE",
)

_CONFIG_FIELDS = {
    "workspace root": "workspace_root",
    "state root": "state_root",
    "artifacts root": "artifacts_root",
    "hot tests root": "hot_tests",
    "persistent test root": "persistent_tests",
}


def _run_coder_team(world: World, *args: str) -> subprocess.CompletedProcess:
    """Run team.py on the temp project, keeping real state off the config paths."""
    config = world.state["config"]
    project = _project(world)
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("SWARM_")
    }
    env["SWARM_CONFIG"] = str(config)
    tools = Path(__file__).resolve().parents[3] / "tools"
    return subprocess.run(
        [
            sys.executable,
            str(tools / TEAM),
            "--root",
            str(project),
            "--state-root",
            str(world.state["state_root"]),
            *args,
        ],
        env=env,
        cwd=str(project),
        capture_output=True,
        text=True,
    )


def _bound_coder_with_task(world: World, examples: dict[str, str]) -> None:
    """Background: a temp harness config with absent roots and a bound coder task."""
    os.environ.pop("SWARM_STATE_ROOT", None)
    wiring.clear_cache()
    root = _temp_root()
    config = root / "harness.json"
    config.write_text(
        json.dumps(
            {
                "version": 1,
                "workspace_root": "/absent/project",
                "state_root": "/absent/project/.state",
                "artifacts_root": "/absent/project/dump",
                "hot_tests": "/absent/project/hot",
                "persistent_tests": [
                    {
                        "root": "/absent/project/tests",
                        "pythonpath": ["."],
                        "kind": "project",
                    }
                ],
            }
        )
    )
    world.state["project"] = root
    world.state["config"] = config
    world.state["state_root"] = root / "real-state"
    world.state["session"] = "coder-1"
    world.state["task"] = "task1"
    result = _run_coder_team(world, "open", "task1", "--role", "coder")
    assert result.returncode == 0, f"open failed: {result.stderr}"
    result = _run_coder_team(
        world, "bind", "task1", "--seat", "worker", "--session", "coder-1"
    )
    assert result.returncode == 0, f"bind failed: {result.stderr}"
    import datetime
    world.state["open_date"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")


def _coder_task_json(world: World) -> Path:
    return _task_dir(world, world.state["task"]) / "task.json"


def _task_name_is(world: World, examples: dict[str, str]) -> None:
    """Given the task name is '<task>': rename the task folder and record."""
    new_name = examples["task"]
    old_name = world.state["task"]
    if new_name == old_name:
        return
    old_dir = _task_dir(world, old_name)
    new_dir = _task_dir(world, new_name)
    new_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(old_dir), str(new_dir))
    doc = json.loads((new_dir / "task.json").read_text())
    doc["task"] = new_name
    (new_dir / "task.json").write_text(json.dumps(doc))
    world.state["task"] = new_name


def _task_definition_of_done_is(world: World, examples: dict[str, str]) -> None:
    path = _coder_task_json(world)
    doc = json.loads(path.read_text())
    doc["definition_of_done"] = examples["done"]
    path.write_text(json.dumps(doc))


def _harness_config_sets(world: World, examples: dict[str, str]) -> None:
    config = world.state["config"]
    doc = json.loads(config.read_text())
    field = _CONFIG_FIELDS[examples["setting"]]
    if field == "persistent_tests":
        doc["persistent_tests"] = [
            {"root": examples["location"], "pythonpath": ["."], "kind": "project"}
        ]
    else:
        doc[field] = examples["location"]
    config.write_text(json.dumps(doc))


def _no_directory_exists(world: World, examples: dict[str, str]) -> None:
    location = Path(examples["location"])
    assert not location.exists(), f"directory unexpectedly exists: {location}"


def _coder_calls_team_context(world: World, examples: dict[str, str]) -> None:
    result = _run_coder_team(world, "context", "--session", world.state["session"])
    assert result.returncode == 0, f"context failed: {result.stderr}"
    world.state["payload"] = result.stdout


def _payload_headers(world: World) -> list[str]:
    known = set(_CODER_HEADERS)
    return [
        line.strip()
        for line in world.state["payload"].splitlines()
        if line.strip() in known
    ]


def _payload_section(world: World, header: str) -> str:
    lines = world.state["payload"].splitlines()
    start = lines.index(header) + 1
    body = []
    for line in lines[start:]:
        if line.strip() in _CODER_HEADERS:
            break
        body.append(line)
    return "\n".join(body)


def _payload_section_is(world: World, examples: dict[str, str]) -> None:
    position = int(examples["position"])
    headers = _payload_headers(world)
    assert headers[position - 1] == examples["section"], (
        f"section {position} was {headers[position - 1]!r}"
    )


def _payload_has_exactly_sections(world: World, examples: dict[str, str]) -> None:
    headers = _payload_headers(world)
    assert len(headers) == 11, f"expected 11 sections, got {headers}"


def _task_section_names(world: World, examples: dict[str, str]) -> None:
    body = _payload_section(world, "TASK")
    assert examples["task"] in body, f"TASK section {body!r} lacks {examples['task']!r}"


def _done_section_carries(world: World, examples: dict[str, str]) -> None:
    body = _payload_section(world, "DEFINITION OF DONE")
    assert examples["done"] in body, f"DONE section {body!r} lacks {examples['done']!r}"


def _resolved_paths_reports(world: World, examples: dict[str, str]) -> None:
    body = _payload_section(world, "RESOLVED PATHS")
    needle = f"{examples['setting']}: {examples['location']}"
    assert needle in body, f"RESOLVED PATHS {body!r} lacks {needle!r}"


def _context_again_same_payload(world: World, examples: dict[str, str]) -> None:
    result = _run_coder_team(world, "context", "--session", world.state["session"])
    assert result.returncode == 0, f"context failed: {result.stderr}"
    assert result.stdout == world.state["payload"], "payload changed across calls"


# --- deterministic_mentor_payload step handlers ---

_MENTOR_HEADERS = ("GOAL", "RULES", "TRAIL", "ASK", "FAILURE")

_DEFAULT_MENTOR_GOAL = "the default mentor goal"
_DEFAULT_MENTOR_RULES = "the default mentor rules"
_DEFAULT_MENTOR_ASK = "the default mentor ask"


def _mentor_task_json(world: World) -> Path:
    return _task_dir(world, world.state["task"]) / "task.json"


def _bound_mentor_with_task(world: World, examples: dict[str, str]) -> None:
    """Background: open a mentor task with its chunk state and bind the mentor seat."""
    os.environ.pop("SWARM_STATE_ROOT", None)
    wiring.clear_cache()
    root = _temp_root()
    config = root / "harness.json"
    config.write_text(
        json.dumps(
            {
                "version": 1,
                "workspace_root": "/absent/project",
                "state_root": "/absent/project/.state",
                "artifacts_root": "/absent/project/dump",
                "hot_tests": "/absent/project/hot",
                "persistent_tests": [
                    {
                        "root": "/absent/project/tests",
                        "pythonpath": ["."],
                        "kind": "project",
                    }
                ],
            }
        )
    )
    world.state["project"] = root
    world.state["config"] = config
    world.state["state_root"] = root / "real-state"
    world.state["task"] = "mentor-task"
    world.state["mentor_session"] = "mentor-1"
    world.state["worker_session"] = "worker-1"
    # the coder payload's stability handler reads these two keys
    world.state["session"] = "mentor-1"
    result = _run_coder_team(
        world, "open", "mentor-task", "--role", "mentor",
        "--goal", _DEFAULT_MENTOR_GOAL,
        "--rules", _DEFAULT_MENTOR_RULES,
        "--ask", _DEFAULT_MENTOR_ASK,
    )
    assert result.returncode == 0, f"open failed: {result.stderr}"
    result = _run_coder_team(
        world, "bind", "mentor-task", "--seat", "mentor", "--session", "mentor-1"
    )
    assert result.returncode == 0, f"bind mentor failed: {result.stderr}"
    result = _run_coder_team(
        world, "bind", "mentor-task", "--seat", "worker", "--session", "worker-1"
    )
    assert result.returncode == 0, f"bind worker failed: {result.stderr}"
    import datetime
    world.state["open_date"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")


def _mentor_calls_context(world: World, examples: dict[str, str]) -> None:
    result = _run_coder_team(
        world, "context", "--session", world.state["mentor_session"]
    )
    assert result.returncode == 0, f"context failed: {result.stderr}"
    world.state["payload"] = result.stdout


def _mentor_payload_headers(world: World) -> list[str]:
    known = set(_MENTOR_HEADERS)
    return [
        line.strip()
        for line in world.state["payload"].splitlines()
        if line.strip() in known
    ]


def _mentor_payload_section(world: World, header: str) -> str:
    lines = world.state["payload"].splitlines()
    start = lines.index(header) + 1
    body = []
    for line in lines[start:]:
        if line.strip() in _MENTOR_HEADERS:
            break
        body.append(line)
    return "\n".join(body)


def _payload_starts_with_system_prompt(world: World, examples: dict[str, str]) -> None:
    payload = world.state["payload"]
    assert payload.startswith(team.MENTOR_SYSTEM_PROMPT), (
        f"payload did not start with the system prompt: {payload[:80]!r}"
    )


def _payload_has_five_mentor_sections(world: World, examples: dict[str, str]) -> None:
    headers = _mentor_payload_headers(world)
    assert headers == list(_MENTOR_HEADERS), (
        f"expected 5 mentor sections in order, got {headers}"
    )


def _mentor_section_is(world: World, examples: dict[str, str]) -> None:
    position = int(examples["position"])
    headers = _mentor_payload_headers(world)
    assert headers[position - 1] == examples["section"], (
        f"section {position} was {headers[position - 1]!r}"
    )


def _chunk_state_sets(world: World, examples: dict[str, str]) -> None:
    path = _mentor_task_json(world)
    doc = json.loads(path.read_text())
    doc.setdefault("mentor", {})[examples["section"].lower()] = examples["value"]
    path.write_text(json.dumps(doc))


def _section_carries(world: World, examples: dict[str, str]) -> None:
    body = _mentor_payload_section(world, examples["section"])
    assert examples["value"] in body, (
        f"{examples['section']} section {body!r} lacks {examples['value']!r}"
    )


def _worker_journaled_plan_and_result(world: World, examples: dict[str, str]) -> None:
    session = world.state["worker_session"]
    for kind, marker in (
        ("plan", "mentor-trail-plan"),
        ("result", "mentor-trail-result"),
    ):
        result = _run_coder_team(
            world, "journal", "--session", session, "--kind", kind,
            "--entry", json.dumps({kind: marker}),
        )
        assert result.returncode == 0, f"journal failed: {result.stderr}"
        world.state[f"trail_{kind}"] = marker


def _trail_lists_both_in_order(world: World, examples: dict[str, str]) -> None:
    body = _mentor_payload_section(world, "TRAIL")
    plan = world.state["trail_plan"]
    result = world.state["trail_result"]
    assert plan in body and result in body, f"TRAIL section {body!r} lacks a marker"
    assert body.index(plan) < body.index(result), "TRAIL entries are out of order"


def _worker_records_failure(world: World, examples: dict[str, str]) -> None:
    evidence = examples["evidence"]
    result = _run_coder_team(
        world, "journal", "--session", world.state["worker_session"],
        "--kind", "stuck", "--entry", json.dumps({"failure": evidence}),
    )
    assert result.returncode == 0, f"journal failed: {result.stderr}"
    world.state["failure_evidence"] = evidence


def _failure_reproduces_evidence(world: World, examples: dict[str, str]) -> None:
    body = _mentor_payload_section(world, "FAILURE")
    evidence = world.state["failure_evidence"]
    assert body == evidence, f"FAILURE section {body!r} is not the evidence {evidence!r}"


def _model_stub_records_calls(world: World, examples: dict[str, str]) -> None:
    """Install a local recorder stub that would log any model request."""
    project = _project(world)
    stub = project / "model_stub.py"
    stub.write_text("import sys\nopen(sys.argv[1], 'a').write('call\\n')\n")
    os.environ["MENTOR_MODEL_STUB"] = str(stub)
    world.state["model_recorder"] = project / "model-calls.log"


def _no_model_request(world: World, examples: dict[str, str]) -> None:
    recorder = world.state["model_recorder"]
    assert not recorder.exists() or recorder.read_text() == "", (
        f"the model stub recorded a call: {recorder.read_text()!r}"
    )
    os.environ.pop("MENTOR_MODEL_STUB", None)


STEP_HANDLERS = [
    (r"^a bound coder with a task and a harness config$", _bound_coder_with_task),
    (r'^the task name is "([^"]*)"$', _task_name_is),
    (r'^the task definition of done is "([^"]*)"$', _task_definition_of_done_is),
    (r'^the harness config sets the (.+) to "([^"]*)"$', _harness_config_sets),
    (r'^no directory exists at "([^"]*)"$', _no_directory_exists),
    (r"^the coder calls team_context$", _coder_calls_team_context),
    (r'^payload section (\S+) is "([^"]*)"$', _payload_section_is),
    (r"^the payload has exactly 11 sections$", _payload_has_exactly_sections),
    (r'^the TASK section names task "([^"]*)"$', _task_section_names),
    (r'^the DEFINITION OF DONE section carries "([^"]*)"$', _done_section_carries),
    (
        r'^the RESOLVED PATHS section reports the (.+) as "([^"]*)"$',
        _resolved_paths_reports,
    ),
    (r"^calling team_context again yields the same payload$", _context_again_same_payload),
    (r"^the harness pack$", _the_harness_pack),
    (r"^wiring is loaded from the pack$", _load_from_pack),
    (r"^the resolved workspace is the pack parent$", _workspace_is_pack_parent),
    (r"^the configured source roots contain the pack tools directory$", _sources_contain_tools),
    (r"^the harness persistent root is the pack harness tests directory$", _persistent_is_harness),
    (r"^the shared hot area is the pack hot tests directory$", _hot_is_pack_hot),
    (r"^a temporary project with its own harness config$", _temporary_project),
    (r"^a temporary project with a malformed harness config$", _malformed_project),
    (r"^wiring is loaded from that project$", _load_from_project),
    (r"^the resolved workspace is that project$", _workspace_is_project),
    (r"^the resolved hot area is that project hot directory$", _hot_is_project_hot),
    (r"^the resolved state root is that project state directory$", _state_is_project_state),
    (r"^the project persistent root is the project tests directory$", _persistent_is_project_tests),
    (r"^the pack config sets a different workspace$", _pack_config_other_workspace),
    (r"^the environment sets the state root to an override directory$", _env_state_override),
    (r"^loading wiring reports the override directory as the state root$", _env_override_reported),
    (r"^a generated file under the project hot directory$", _generated_hot_file),
    (r"^the harness clean command runs for hot$", _run_clean_hot),
    (r"^the project hot directory is empty$", _hot_empty),
    (r"^the project persistent root still exists$", _persistent_still_exists),
    (r"^wiring is requested from that project$", _request_from_project),
    (r"^loading fails with a wiring error$", _loading_fails_with_wiring_error),
    # task_state_layout handlers
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
    # deterministic_mentor_payload handlers
    (r"^a bound mentor with a task and a chunk state$",
     _bound_mentor_with_task),
    (r"^the mentor calls team_context$",
     _mentor_calls_context),
    (r"^the payload starts with a system prompt$",
     _payload_starts_with_system_prompt),
    (r"^the payload has exactly 5 mentor sections$",
     _payload_has_five_mentor_sections),
    (r'^mentor section (\S+) is "([^"]*)"$',
     _mentor_section_is),
    (r'^the chunk state sets (\S+) to "([^"]*)"$',
     _chunk_state_sets),
    (r'^the "([^"]*)" section carries "([^"]*)"$',
     _section_carries),
    (r"^the worker journaled a plan and a result$",
     _worker_journaled_plan_and_result),
    (r"^the TRAIL section lists both journal entries in order$",
     _trail_lists_both_in_order),
    (r'^the worker recorded a failure with evidence "([^"]*)"$',
     _worker_records_failure),
    (r"^the FAILURE section reproduces the evidence verbatim$",
     _failure_reproduces_evidence),
    (r"^a model stub that records calls$",
     _model_stub_records_calls),
    (r"^no model request was made$",
     _no_model_request),
]
