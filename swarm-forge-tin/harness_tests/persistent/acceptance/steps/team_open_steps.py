"""Step handlers for the team open sections acceptance feature.

The handlers write a brief/design file with the section headings the scenario
names, then run ``team.py open`` and read the fields back out of ``task.json``.
The section parsing itself lives in ``team.extract_section``.
"""

import datetime
import json

from runtime import World

from .common import _run_team, _task_json, _temp_root, step_values


def _brief_path(world: World):
    return world.state.setdefault("brief_path", _temp_root() / "brief.md")


def _design_path(world: World):
    return world.state.setdefault("design_path", _temp_root() / "design.md")


def _write_brief(world: World, text: str) -> None:
    _brief_path(world).write_text(text)


def _append_brief(world: World, text: str) -> None:
    with _brief_path(world).open("a") as handle:
        handle.write(text)


def _write_design(world: World, text: str) -> None:
    _design_path(world).write_text(text)


def _append_design(world: World, text: str) -> None:
    with _design_path(world).open("a") as handle:
        handle.write(text)


def _brief_task(world: World, examples: dict[str, str]) -> None:
    (value,) = step_values(
        examples, r'^a brief whose TASK section reads "([^"]*)"$'
    )
    _write_brief(world, f"# TASK\n{value}\n")


def _brief_definition(world: World, examples: dict[str, str]) -> None:
    (value,) = step_values(
        examples, r'^the brief also defines DEFINITION OF DONE as "([^"]*)"$'
    )
    _append_brief(world, f"\n# DEFINITION OF DONE\n{value}\n")


def _design_contract(world: World, examples: dict[str, str]) -> None:
    (value,) = step_values(
        examples,
        r'^a design whose INTERFACE CONTRACT section reads "([^"]*)"$',
    )
    _write_design(world, f"# INTERFACE CONTRACT\n{value}\n")


def _design_files(world: World, examples: dict[str, str]) -> None:
    (value,) = step_values(
        examples, r'^the design also defines FILES as "([^"]*)"$'
    )
    _append_design(world, f"\n# FILES\n{value}\n")


def _brief_section(world: World, examples: dict[str, str]) -> None:
    section, value = step_values(
        examples,
        r'^a brief with a "([^"]*)" section reading "([^"]*)"$',
    )
    _write_brief(world, f"# {section}\n{value}\n")


def _brief_styled_task(world: World, examples: dict[str, str]) -> None:
    style, value = step_values(
        examples,
        r'^a brief with a "([^"]*)" TASK heading reading "([^"]*)"$',
    )
    headings = {"markdown": "# TASK", "bold": "**TASK**", "plain": "TASK"}
    assert style in headings, f"unknown heading style: {style}"
    _write_brief(world, f"{headings[style]}\n{value}\n")


def _brief_without_headings(world: World, examples: dict[str, str]) -> None:
    _write_brief(world, "Some prose without any section headings.\n")


def _open_command(world: World, cmd: list[str]) -> None:
    task = cmd[1]
    result = _run_team(world, *cmd)
    assert result.returncode == 0, f"open failed: {result.stderr}"
    world.state["open_date"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    world.state["task"] = task


def _with_inputs(world: World, cmd: list[str]) -> list[str]:
    if "brief_path" in world.state:
        cmd += ["--brief", str(world.state["brief_path"])]
    if "design_path" in world.state:
        cmd += ["--design", str(world.state["design_path"])]
    return cmd


def _open_with_inputs(world: World, examples: dict[str, str]) -> None:
    task, role = step_values(
        examples,
        r'^the orchestrator opens task "([^"]*)" for role "([^"]*)" with the '
        r"given inputs$",
    )
    _open_command(world, _with_inputs(world, ["open", task, "--role", role]))


def _open_with_flags(world: World, examples: dict[str, str]) -> None:
    task, role = step_values(
        examples,
        r'^the orchestrator opens task "([^"]*)" for role "([^"]*)" with '
        r"explicit flags$",
    )
    cmd = [
        "open",
        task,
        "--role",
        role,
        "--task-text",
        "explicit text",
        "--definition",
        "explicit done",
        "--interface",
        "explicit contract",
        "--files",
        "explicit files",
        "--goal",
        "explicit goal",
    ]
    _open_command(world, _with_inputs(world, cmd))


def _task_doc(world: World) -> dict:
    return json.loads(_task_json(world).read_text())


def _opened_task_text(world: World, examples: dict[str, str]) -> None:
    (value,) = step_values(examples, r'^the opened task text is "([^"]*)"$')
    assert _task_doc(world).get("task_text") == value


def _opened_definition(world: World, examples: dict[str, str]) -> None:
    (value,) = step_values(
        examples, r'^the opened definition of done is "([^"]*)"$'
    )
    assert _task_doc(world).get("definition_of_done") == value


def _opened_contract(world: World, examples: dict[str, str]) -> None:
    (value,) = step_values(
        examples, r'^the opened interface contract is "([^"]*)"$'
    )
    assert _task_doc(world).get("interface_contract") == value


def _opened_files(world: World, examples: dict[str, str]) -> None:
    (value,) = step_values(examples, r'^the opened files field is "([^"]*)"$')
    assert _task_doc(world).get("files") == value


def _opened_mentor(world: World, examples: dict[str, str]) -> None:
    section, value = step_values(
        examples, r'^the opened mentor field "([^"]*)" is "([^"]*)"$'
    )
    mentor = _task_doc(world).get("mentor", {})
    assert mentor.get(section.lower()) == value, mentor


def _opened_task_empty(world: World, examples: dict[str, str]) -> None:
    doc = _task_doc(world)
    assert not doc.get("task_text"), doc.get("task_text")
    assert doc.get("definition_of_done") == "", doc.get("definition_of_done")


HANDLERS = [
    (r'^a brief whose TASK section reads "([^"]*)"$', _brief_task),
    (
        r'^the brief also defines DEFINITION OF DONE as "([^"]*)"$',
        _brief_definition,
    ),
    (
        r'^a design whose INTERFACE CONTRACT section reads "([^"]*)"$',
        _design_contract,
    ),
    (r'^the design also defines FILES as "([^"]*)"$', _design_files),
    (r'^a brief with a "([^"]*)" section reading "([^"]*)"$', _brief_section),
    (
        r'^a brief with a "([^"]*)" TASK heading reading "([^"]*)"$',
        _brief_styled_task,
    ),
    (r"^a brief with no section headings$", _brief_without_headings),
    (
        r'^the orchestrator opens task "([^"]*)" for role "([^"]*)" with the '
        r"given inputs$",
        _open_with_inputs,
    ),
    (
        r'^the orchestrator opens task "([^"]*)" for role "([^"]*)" with '
        r"explicit flags$",
        _open_with_flags,
    ),
    (r'^the opened task text is "([^"]*)"$', _opened_task_text),
    (r'^the opened definition of done is "([^"]*)"$', _opened_definition),
    (r'^the opened interface contract is "([^"]*)"$', _opened_contract),
    (r'^the opened files field is "([^"]*)"$', _opened_files),
    (r'^the opened mentor field "([^"]*)" is "([^"]*)"$', _opened_mentor),
    (
        r"^the opened task text and definition of done are empty$",
        _opened_task_empty,
    ),
]
