"""Step handlers for the harness CLI acceptance feature.

Every handler either runs the ``harness`` CLI and reads back its own output, or
builds the temp project the scenario describes. The only parsing here is reading
the status rows the CLI prints, which no module exposes in-process.
"""

import json
import re

import wiring
from runtime import World

from .common import (
    _project,
    _run_harness,
    _temp_harness,
    _temp_root,
    step_values,
)

_STATUS_ROW_RE = re.compile(r"^(\S+)\s+\[(ok|-)\]\s+(.*)$")
_MANAGED_TARGETS = ("hot", "artifacts", "state")


def _make_full_project(world: World) -> None:
    root = _temp_root()
    (root / "tools").mkdir(parents=True)
    (root / "tools" / "wiring.py").write_text("")
    for name in ("tests", "hot", "dump", "state"):
        (root / name).mkdir()
    config = {
        "version": 1,
        "workspace_root": ".",
        "state_root": "state",
        "artifacts_root": "dump",
        "hot_tests": "hot",
        "persistent_tests": [
            {"root": "tests", "pythonpath": ["."], "kind": "project"}
        ],
        "source_roots": ["tools"],
    }
    config_path = root / "harness.json"
    config_path.write_text(json.dumps(config))
    world.state["project"] = root
    world.state["config"] = config_path
    world.state["pack"] = root
    world.state["managed_dirs"] = {
        "hot": root / "hot",
        "artifacts": root / "dump",
        "state": root / "state",
    }
    world.state["state_dir"] = root / "state"
    world.state["artifacts_dir"] = root / "dump"
    world.state["hot_dir"] = root / "hot"


def _managed_dir(world: World, name: str):
    """Return the managed area a clean target names, inside the temp project."""
    managed = world.state.get("managed_dirs")
    if managed and name in managed:
        return managed[name]
    return _project(world) / name


def _all_roots_inside(world: World, examples: dict[str, str]) -> None:
    _make_full_project(world)


def _absent_roots(world: World, examples: dict[str, str]) -> None:
    _temp_harness(world)


def _run_config(world: World, examples: dict[str, str]) -> None:
    world.state["cli_result"] = _run_harness(world, "config")


def _config_is_resolved_json(world: World, examples: dict[str, str]) -> None:
    result = world.state["cli_result"]
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    expected = wiring.load(config=world.state["config"]).as_dict()
    assert payload == expected


def _run_status(world: World, examples: dict[str, str]) -> None:
    world.state["cli_result"] = _run_harness(world, "status")


def parse_status_rows(stdout: str) -> dict[str, tuple[str, str]]:
    """Map each status row label to its ``(marker, path)`` pair."""
    rows = {}
    for line in stdout.splitlines():
        match = _STATUS_ROW_RE.match(line.strip())
        if match:
            label, marker, path = match.groups()
            rows[label] = (marker, path)
    return rows


def _status_rows(world: World) -> dict[str, tuple[str, str]]:
    result = world.state["cli_result"]
    assert result.returncode == 0, result.stderr
    return parse_status_rows(result.stdout)


def _status_reports_rows(world: World, examples: dict[str, str]) -> None:
    rows = _status_rows(world)
    expected = {"PACK", "CONFIG", "WORKSPACE", "STATE", "ARTIFACTS", "HOT"}
    assert expected <= set(rows), rows


def _status_marks_row(world: World, examples: dict[str, str]) -> None:
    row, marker = step_values(
        examples, r'^the status marks the (\S+) row as "([^"]*)"$'
    )
    rows = _status_rows(world)
    assert row in rows, f"no status row for {row!r}: {sorted(rows)}"
    assert rows[row][0] == marker, f"{row} row is {rows[row]!r}, expected {marker!r}"


def _in_process_mail_item(world: World, examples: dict[str, str]) -> None:
    inbox = world.state["state_dir"] / "mail" / "inbox" / "coder" / "in_process"
    inbox.mkdir(parents=True)
    item = inbox / "01_item.json"
    item.write_text("{}")
    world.state["in_process_item"] = item


def _run_clean_target(world: World, examples: dict[str, str]) -> None:
    (target,) = step_values(examples, r'^the harness clean command runs for (\S+)$')
    world.state["cli_result"] = _run_harness(world, "clean", target)


def _run_clean_default(world: World, examples: dict[str, str]) -> None:
    world.state["cli_result"] = _run_harness(world, "clean")


def _clean_exits_with(world: World, examples: dict[str, str]) -> None:
    (exit_code,) = step_values(
        examples,
        r"^the harness clean command (?:refuses with|completes and exits with) "
        r"(?:exit )?code (.+)$",
    )
    result = world.state["cli_result"]
    assert result.returncode == int(exit_code), (
        f"clean exited {result.returncode}, expected {exit_code}: {result.stderr}"
    )


def _refusal_reports_item(world: World, examples: dict[str, str]) -> None:
    result = world.state["cli_result"]
    output = f"{result.stdout}\n{result.stderr}"
    assert "in-process item" in output, (
        f"the refusal does not report the in-process item: {output!r}"
    )
    state_dir = str(world.state["state_dir"])
    assert state_dir in output, (
        f"the refusal does not name the state directory {state_dir}: {output!r}"
    )


def _state_holds_item(world: World, examples: dict[str, str]) -> None:
    item = world.state.get("in_process_item")
    if item is not None:
        assert item.exists()
        return
    # The in-process item is the live team task the open step filed.
    task = world.state.get("task")
    assert task, "no in-process item was recorded"
    task_dir = (
        world.state["state_dir"]
        / "tasks"
        / world.state.get("open_date", "unknown")
        / task
    )
    assert task_dir.is_dir(), f"state directory lost the live task: {task_dir}"


def _run_clean_state_force(world: World, examples: dict[str, str]) -> None:
    world.state["cli_result"] = _run_harness(world, "clean", "state", "--force")


def _write_generated(directory) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "generated.json").write_text("{}")


def _assert_empty(directory) -> None:
    assert directory.is_dir(), f"{directory} is not a directory"
    assert list(directory.iterdir()) == [], f"{directory} is not empty"


def _generated_file(world: World, examples: dict[str, str]) -> None:
    (target,) = step_values(
        examples, r'^a generated file under the project (\S+) directory$'
    )
    _write_generated(_managed_dir(world, target))


def _generated_files_all(world: World, examples: dict[str, str]) -> None:
    for target in _MANAGED_TARGETS:
        _write_generated(_managed_dir(world, target))


def _dir_empty(world: World, examples: dict[str, str]) -> None:
    (target,) = step_values(
        examples, r'^the project (\S+) directory is empty$'
    )
    _assert_empty(_managed_dir(world, target))


def _all_dirs_empty(world: World, examples: dict[str, str]) -> None:
    for target in _MANAGED_TARGETS:
        _assert_empty(_managed_dir(world, target))


HANDLERS = [
    (r"^a temporary project with all harness roots inside it$", _all_roots_inside),
    (r"^a temporary project whose configured roots are absent$", _absent_roots),
    (r"^the harness config command runs$", _run_config),
    (r"^the config output is the resolved wiring as JSON$", _config_is_resolved_json),
    (r"^the harness status command runs$", _run_status),
    (
        r"^the status reports a row for the pack, config, workspace, state, "
        r"artifacts, and hot$",
        _status_reports_rows,
    ),
    (r'^the status marks the (\S+) row as "([^"]*)"$', _status_marks_row),
    (r"^an in-process mail item under the project state directory$", _in_process_mail_item),
    (r'^the harness clean command runs for (\S+)$', _run_clean_target),
    (r'^the harness clean command runs with no target$', _run_clean_default),
    (
        r"^the harness clean command (?:refuses with|completes and exits with) "
        r"(?:exit )?code (.+)$",
        _clean_exits_with,
    ),
    (r"^the project state directory still holds the in-process item$", _state_holds_item),
    (r"^the refusal reports the in-process item$", _refusal_reports_item),
    (r"^the harness clean command force-cleans the state area$", _run_clean_state_force),
    (r'^a generated file under the project (\S+) directory$', _generated_file),
    (
        r"^generated files under the project hot, artifacts, and state directories$",
        _generated_files_all,
    ),
    (r'^the project (\S+) directory is empty$', _dir_empty),
    (
        r"^the project hot, artifacts, and state directories are empty$",
        _all_dirs_empty,
    ),
]
