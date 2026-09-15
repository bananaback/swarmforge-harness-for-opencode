"""Step handlers for the task-breaker bridge acceptance feature.

Each handler delegates to ``taskbreak.py`` through the CLI and reads back the
tool's own output and the task folders it opens. The only logic here builds the
plan fixtures the scenarios describe and translates the feature's assertion
vocabulary (a task.json field name, an ORACLE section) into a check on what the
tool wrote.
"""

import datetime
import json

import taskbreak
from runtime import World

from .common import _only_dir, _project, _run_tool, _task_dir, step_values

TASKBREAK = "taskbreak.py"
PLAN_NAME = "cart.plan.json"
PLAN_FEATURE = "features/cart.feature"
OTHER_FEATURE = "features/other.feature"

VALID_BRIEF = "TASK\nBuild Cart.\n\nDEFINITION OF DONE\n- [ ] total\n"
VALID_DESIGN = "INTERFACE CONTRACT\nclass Cart: ...\n\nFILES\n- src/cart.py -- Cart\n"
VALID_ORACLE = "pytest unit/test_cart.py -q"
VALID_GOAL = "make the cart total green"
VALID_RULES = "one job per method"

_TASK_FIELDS = {
    "definition of done": ("definition_of_done",),
    "interface contract": ("interface_contract",),
    "files": ("files",),
    "mentor goal": ("mentor", "goal"),
    "mentor rules": ("mentor", "rules"),
}
_OPENED_PREFIX = "OPENED: "


# --- plan fixtures ----------------------------------------------------------


def _write_feature(world: World, name: str) -> None:
    feature = _project(world) / name
    feature.parent.mkdir(parents=True, exist_ok=True)
    feature.write_text("Feature: Cart\n  Scenario: total\n")


def _chunk(task: str, role: str, **overrides) -> dict:
    entry = {
        "task": task,
        "role": role,
        "brief_text": VALID_BRIEF,
        "design_text": VALID_DESIGN,
        "oracle": VALID_ORACLE,
        "goal": VALID_GOAL,
        "rules": VALID_RULES,
    }
    entry.update(overrides)
    return entry


def _write_plan(world: World, chunks, feature=PLAN_FEATURE, version=1, seed=True):
    if seed and feature:
        _write_feature(world, feature)
    plan = {"version": version, "feature": feature, "chunks": chunks}
    path = _project(world) / PLAN_NAME
    path.write_text(json.dumps(plan))
    world.state["plan"] = path
    world.state["plan_task"] = chunks[0]["task"] if chunks else None


def _append_chunk(world: World, chunk: dict) -> None:
    path = world.state["plan"]
    plan = json.loads(path.read_text())
    plan["chunks"].append(chunk)
    path.write_text(json.dumps(plan))


# --- opening ----------------------------------------------------------------


def _run_taskbreak(world: World, *args: str):
    result = _run_tool(
        world, TASKBREAK, "--plan", str(world.state["plan"]), *args
    )
    world.state["taskbreak_result"] = result
    if result.returncode == 0:
        world.state["open_date"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    return result


def _opened_tasks(stdout: str) -> list[str]:
    return [
        line[len(_OPENED_PREFIX):]
        for line in stdout.splitlines()
        if line.startswith(_OPENED_PREFIX)
    ]


def _staging_dir(world: World):
    return taskbreak.staging_dir(str(_project(world)), str(world.state["plan"]))


def _field_value(doc: dict, path: tuple):
    value = doc
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


# --- Given ------------------------------------------------------------------


def _plan_with_valid_chunk(world: World, examples: dict[str, str]) -> None:
    task, role = step_values(
        examples,
        r'^a task-breaker plan with a valid chunk "([^"]*)" for role "([^"]*)"$',
    )
    _write_plan(world, [_chunk(task, role)])


def _plan_with_designless_chunk(world: World, examples: dict[str, str]) -> None:
    task, role = step_values(
        examples,
        r'^a task-breaker plan with a design-less chunk "([^"]*)" for role "([^"]*)"$',
    )
    _write_plan(world, [_chunk(task, role, design_text=None)])


def _plan_with_no_chunks(world: World, examples: dict[str, str]) -> None:
    _write_plan(world, [])


def _plan_with_duplicated_task(world: World, examples: dict[str, str]) -> None:
    (task,) = step_values(
        examples, r'^a task-breaker plan with a duplicated task "([^"]*)"$'
    )
    _write_plan(world, [_chunk(task, "coder"), _chunk(task, "refactorer")])


def _plan_with_unsupported_role(world: World, examples: dict[str, str]) -> None:
    (role,) = step_values(
        examples, r'^a task-breaker plan with an unsupported role "([^"]*)"$'
    )
    _write_plan(world, [_chunk("cart-domain", role)])


def _plan_referencing_missing(world: World, examples: dict[str, str]) -> None:
    (reference,) = step_values(
        examples, r'^a task-breaker plan referencing a missing "([^"]*)"$'
    )
    if reference == "brief":
        chunk = _chunk("cart-domain", "coder", brief_text=None, brief="missing.brief.md")
        _write_plan(world, [chunk])
    else:
        _write_plan(
            world,
            [_chunk("cart-domain", "coder")],
            feature="features/missing.feature",
            seed=False,
        )


def _plan_with_existing_oracle(world: World, examples: dict[str, str]) -> None:
    brief = f"{VALID_BRIEF}\nORACLE\nold oracle\n"
    _write_plan(world, [_chunk("cart-domain", "coder", brief_text=brief)])


def _plan_with_chunk_feature(world: World, examples: dict[str, str]) -> None:
    _write_feature(world, OTHER_FEATURE)
    _write_plan(
        world,
        [_chunk("cart-domain", "coder", feature=OTHER_FEATURE)],
    )


def _plan_invalid_json(world: World, examples: dict[str, str]) -> None:
    path = _project(world) / PLAN_NAME
    path.write_text("{not json")
    world.state["plan"] = path


def _plan_with_version(world: World, examples: dict[str, str]) -> None:
    (version,) = step_values(
        examples, r'^a task-breaker plan with schema version "([^"]*)"$'
    )
    _write_plan(world, [_chunk("cart-domain", "coder")], version=int(version))


def _plan_holds_another_chunk(world: World, examples: dict[str, str]) -> None:
    task, role = step_values(
        examples,
        r'^the plan holds another valid chunk "([^"]*)" for role "([^"]*)"$',
    )
    _append_chunk(world, _chunk(task, role))


def _plan_holds_briefless_chunk(world: World, examples: dict[str, str]) -> None:
    _append_chunk(world, {"task": "cart-repo", "role": "refactorer"})


# --- When -------------------------------------------------------------------


def _open_plan(world: World, examples: dict[str, str]) -> None:
    _run_taskbreak(world)


def _open_plan_dry(world: World, examples: dict[str, str]) -> None:
    _run_taskbreak(world, "--dry-run")


def _open_plan_json(world: World, examples: dict[str, str]) -> None:
    _run_taskbreak(world, "--json")


# --- Then -------------------------------------------------------------------


def _bridge_reports_opened(world: World, examples: dict[str, str]) -> None:
    (tasks,) = step_values(
        examples, r'^the bridge reports the opened tasks "([^"]*)"$'
    )
    expected = [item.strip() for item in tasks.split(",")]
    result = world.state["taskbreak_result"]
    assert result.returncode == 0, result.stderr
    actual = _opened_tasks(result.stdout)
    assert actual == expected, f"opened {actual} != {expected}"


def _team_task_exists(world: World, examples: dict[str, str]) -> None:
    task, role = step_values(
        examples, r'^team task "([^"]*)" exists for role "([^"]*)"$'
    )
    doc = json.loads((_task_dir(world, task) / "task.json").read_text())
    assert doc["role"] == role, f"role {doc['role']!r} != {role!r}"


def _opened_task_records(world: World, examples: dict[str, str]) -> None:
    field, value = step_values(
        examples, r'^the opened task records (.+) "([^"]*)"$'
    )
    doc = json.loads(
        (_task_dir(world, world.state["plan_task"]) / "task.json").read_text()
    )
    actual = _field_value(doc, _TASK_FIELDS[field])
    assert actual == value, f"{field} {actual!r} != {value!r}"


def _bridge_refused(world: World, examples: dict[str, str]) -> None:
    (problem,) = step_values(
        examples, r'^the bridge is refused with a problem naming "([^"]*)"$'
    )
    result = world.state["taskbreak_result"]
    assert result.returncode == 2, f"bridge was not refused: {result.stdout}"
    assert problem in result.stderr, result.stderr


def _bridge_opens_nothing(world: World, examples: dict[str, str]) -> None:
    tasks_root = _project(world) / "state" / "tasks"
    opened = list(tasks_root.rglob("task.json")) if tasks_root.is_dir() else []
    assert not opened, f"tasks were opened: {opened}"


def _staged_inputs_land(world: World, examples: dict[str, str]) -> None:
    (relative,) = step_values(
        examples, r'^the staged inputs land under "([^"]*)"$'
    )
    staging = _staging_dir(world)
    assert staging.is_dir(), f"no staged inputs under {staging}"
    assert staging.as_posix().endswith(relative), f"{staging} is not under {relative}"


def _staged_brief_one_oracle(world: World, examples: dict[str, str]) -> None:
    (name,) = step_values(
        examples, r'^the staged brief "([^"]*)" carries exactly one ORACLE section$'
    )
    text = (_staging_dir(world) / name).read_text()
    count = sum(
        1
        for line in text.splitlines()
        if line.strip().upper() == taskbreak.ORACLE_HEADER
    )
    assert count == 1, f"{name} carries {count} ORACLE sections"


def _staged_design_exists(world: World, examples: dict[str, str]) -> None:
    (name,) = step_values(examples, r'^the staged design "([^"]*)" exists$')
    assert (_staging_dir(world) / name).is_file(), f"{name} was not staged"


def _bridge_reports(world: World, examples: dict[str, str]) -> None:
    (expected,) = step_values(examples, r'^the bridge reports "([^"]*)"$')
    assert expected in world.state["taskbreak_result"].stdout


def _bridge_emits_json(world: World, examples: dict[str, str]) -> None:
    (tasks,) = step_values(
        examples, r'^the bridge emits JSON naming the opened tasks "([^"]*)"$'
    )
    expected = [item.strip() for item in tasks.split(",")]
    result = world.state["taskbreak_result"]
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["opened"] == expected


def _chunk_input_only_feature(world: World, examples: dict[str, str]) -> None:
    (name,) = step_values(
        examples, r'^the chunk input holds only the feature "([^"]*)"$'
    )
    input_dir = _only_dir(_task_dir(world, world.state["plan_task"])) / "input"
    features = sorted(path.name for path in input_dir.glob("*.feature"))
    assert features == [name], f"chunk input holds {features} != [{name}]"


HANDLERS = [
    (
        r'^a task-breaker plan with a valid chunk "([^"]*)" for role "([^"]*)"$',
        _plan_with_valid_chunk,
    ),
    (
        r'^a task-breaker plan with a design-less chunk "([^"]*)" for role "([^"]*)"$',
        _plan_with_designless_chunk,
    ),
    (r"^a task-breaker plan with no chunks$", _plan_with_no_chunks),
    (
        r'^a task-breaker plan with a duplicated task "([^"]*)"$',
        _plan_with_duplicated_task,
    ),
    (
        r'^a task-breaker plan with an unsupported role "([^"]*)"$',
        _plan_with_unsupported_role,
    ),
    (
        r'^a task-breaker plan referencing a missing "([^"]*)"$',
        _plan_referencing_missing,
    ),
    (
        r"^a task-breaker plan whose chunk brief already carries an oracle$",
        _plan_with_existing_oracle,
    ),
    (
        r"^a task-breaker plan whose chunk overrides the plan feature$",
        _plan_with_chunk_feature,
    ),
    (
        r"^a task-breaker plan that is not valid JSON$",
        _plan_invalid_json,
    ),
    (
        r'^a task-breaker plan with schema version "([^"]*)"$',
        _plan_with_version,
    ),
    (
        r'^the plan holds another valid chunk "([^"]*)" for role "([^"]*)"$',
        _plan_holds_another_chunk,
    ),
    (r"^the plan holds a brief-less chunk$", _plan_holds_briefless_chunk),
    (r"^the task-breaker plan is opened$", _open_plan),
    (r"^the task-breaker plan is opened as a dry run$", _open_plan_dry),
    (r"^the task-breaker plan is opened with JSON output$", _open_plan_json),
    (
        r'^the bridge reports the opened tasks "([^"]*)"$',
        _bridge_reports_opened,
    ),
    (
        r'^team task "([^"]*)" exists for role "([^"]*)"$',
        _team_task_exists,
    ),
    (r'^the opened task records (.+) "([^"]*)"$', _opened_task_records),
    (
        r'^the bridge is refused with a problem naming "([^"]*)"$',
        _bridge_refused,
    ),
    (r"^the bridge opens nothing$", _bridge_opens_nothing),
    (r'^the staged inputs land under "([^"]*)"$', _staged_inputs_land),
    (
        r'^the staged brief "([^"]*)" carries exactly one ORACLE section$',
        _staged_brief_one_oracle,
    ),
    (r'^the staged design "([^"]*)" exists$', _staged_design_exists),
    (r'^the bridge reports "([^"]*)"$', _bridge_reports),
    (
        r'^the bridge emits JSON naming the opened tasks "([^"]*)"$',
        _bridge_emits_json,
    ),
    (
        r'^the chunk input holds only the feature "([^"]*)"$',
        _chunk_input_only_feature,
    ),
]
