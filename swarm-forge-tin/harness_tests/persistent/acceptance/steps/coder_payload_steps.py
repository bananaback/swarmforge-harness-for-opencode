"""Step handlers for the deterministic coder payload acceptance feature."""

import json
import shutil
from pathlib import Path

from runtime import World

from .common import (
    _run_coder_team,
    _section_body,
    _task_dir,
    _task_json,
    _temp_harness,
)

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


def _bound_coder_with_task(world: World, examples: dict[str, str]) -> None:
    """Background: a temp harness config with absent roots and a bound coder task."""
    _temp_harness(world)
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
    path = _task_json(world)
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
    return _section_body(world.state["payload"], _CODER_HEADERS, header)


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


HANDLERS = [
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
]
