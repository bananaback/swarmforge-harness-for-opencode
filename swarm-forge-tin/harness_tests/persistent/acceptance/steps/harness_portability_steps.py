"""Step handlers for the harness portability acceptance feature.

The feature proves that a ``harness.json`` config is the single source of
resolution: switching configs switches the workspace and the persistent test
root, the shared areas stay in the pack, and the committed todo sample runs its
own acceptance pipeline without a file being written into the sample tree.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import wiring
from runtime import World

from .common import _temp_root, step_values

PACK = wiring.PACK_ROOT
TODO_CONFIG = PACK / "harness.todo.json"
TODO_SAMPLE = PACK.parent / "samples" / "todo"
PROJECT_RUNNER = (
    PACK / "project_tests" / "persistent" / "acceptance" / "run_acceptance.py"
)

_AREA_FIELDS = {
    "artifacts": "artifacts_root",
    "hot": "hot_tests",
    "state": "state_root",
}


def _pack_configs(world: World, examples: dict[str, str]) -> None:
    """Record the pack's own config and the todo config fixture."""
    pack = wiring.PACK_ROOT
    configs = {"pack": pack / "harness.json", "todo": pack / "harness.todo.json"}
    for name, config in configs.items():
        assert config.is_file(), f"missing {name} config: {config}"
    world.state["pack"] = pack
    world.state["configs"] = configs


def _load_through_config(world: World, examples: dict[str, str]) -> None:
    """Load wiring through the named config and record the resolution."""
    (name,) = step_values(examples, r"^wiring is loaded through the (.+) config$")
    wiring.clear_cache()
    world.state["resolved"] = wiring.load(config=world.state["configs"][name])


def _resolved_workspace(world: World, examples: dict[str, str]) -> None:
    """Assert the workspace the config selects.

    The step carries a ``<workspace>`` placeholder, so the registered pattern
    matches that raw shape and the example value is resolved here. Both example
    rows are served by this handler.
    """
    (workspace,) = step_values(examples, r"^the resolved workspace is the (.+)$")
    if workspace == "pack parent":
        expected = world.state["pack"].parent
    elif workspace == "todo sample":
        expected = TODO_SAMPLE
    else:
        raise AssertionError(f"unknown workspace: {workspace}")
    resolved = world.state["resolved"]
    assert resolved.workspace_root == expected, (
        f"resolved workspace is {resolved.workspace_root}, expected {expected}"
    )


def _project_with_persistent_location(
    world: World, examples: dict[str, str]
) -> None:
    """Build a temp project plus pack whose config points the root at a location."""
    (location,) = step_values(
        examples,
        r"^a temporary project whose config places its persistent root in the (.+)$",
    )
    root = _temp_root()
    project = root / "project"
    project.mkdir()
    pack = root / "pack"
    (pack / "tools").mkdir(parents=True)
    (pack / "tools" / "wiring.py").write_text("")
    if location == "pack":
        os.environ["SWARM_PACK"] = str(pack)
        persistent = pack / "tests"
    elif location == "project":
        persistent = project / "tests"
    else:
        raise AssertionError(f"unknown persistent location: {location}")
    persistent.mkdir(parents=True)
    config_path = project / "harness.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "workspace_root": ".",
                "persistent_tests": [
                    {
                        "root": str(persistent),
                        "pythonpath": ["."],
                        "kind": "project",
                    }
                ],
            }
        )
    )
    world.state["config_path"] = config_path
    world.state["pack"] = pack
    world.state["location_dirs"] = {"project": project, "pack": pack}


def _load_wired_config(world: World, examples: dict[str, str]) -> None:
    """Load the config the temp project placed, and record the resolution."""
    wiring.clear_cache()
    world.state["resolved"] = wiring.load(config=world.state["config_path"])


def _selected_inside(world: World, examples: dict[str, str]) -> None:
    """Assert the selected persistent root sits under the named location."""
    (location,) = step_values(
        examples, r"^the selected persistent root is inside the (.+)$"
    )
    selected = world.state.get("selected_persistent")
    assert selected is not None, "no persistent root was selected"
    inside = world.state["location_dirs"][location]
    assert Path(selected).is_relative_to(inside), f"{selected} is not inside {inside}"


def _todo_wired(world: World, examples: dict[str, str]) -> None:
    """Record the pack and the committed todo config fixture."""
    assert TODO_CONFIG.is_file(), f"missing todo config: {TODO_CONFIG}"
    world.state["pack"] = wiring.PACK_ROOT
    world.state["todo_config"] = TODO_CONFIG


def _todo_resolved(world: World, examples: dict[str, str]) -> None:
    """Resolve the todo config and record the resolution."""
    wiring.clear_cache()
    world.state["resolved"] = wiring.load(config=world.state["todo_config"])


def _resolved_area_in_pack(world: World, examples: dict[str, str]) -> None:
    """Assert a resolved shared area stays inside the harness pack."""
    (area,) = step_values(
        examples, r"^the resolved (.+) path is inside the harness pack$"
    )
    value = getattr(world.state["resolved"], _AREA_FIELDS[area])
    assert value is not None, f"the resolved {area} path is unset"
    assert Path(value).is_relative_to(world.state["pack"]), (
        f"the resolved {area} path {value} is not inside {world.state['pack']}"
    )


def _pipeline_runs(world: World, examples: dict[str, str]) -> None:
    """Run the todo project acceptance pipeline with the shared hot area isolated."""
    hot = _temp_root() / "hot"
    hot.mkdir(parents=True, exist_ok=True)
    env = {
        key: value for key, value in os.environ.items() if not key.startswith("SWARM_")
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["SWARM_HOT"] = str(hot)
    world.state["pipeline_result"] = subprocess.run(
        [
            sys.executable,
            str(PROJECT_RUNNER),
            "--config",
            str(world.state["todo_config"]),
        ],
        cwd=str(PACK),
        env=env,
        capture_output=True,
        text=True,
    )


def _pipeline_passes(world: World, examples: dict[str, str]) -> None:
    """Assert the todo pipeline exited cleanly."""
    result = world.state["pipeline_result"]
    assert result.returncode == 0, (
        f"todo pipeline exited {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def _snapshot(root: Path) -> dict[str, str]:
    """Map every file under ``root`` to the sha256 of its bytes."""
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _sample_snapshot(world: World, examples: dict[str, str]) -> None:
    """Record the todo sample root and a digest of every file under it."""
    root = wiring.load(config=world.state["todo_config"]).workspace_root
    world.state["sample_root"] = root
    world.state["sample_snapshot"] = _snapshot(root)


def _sample_unchanged(world: World, examples: dict[str, str]) -> None:
    """Assert the todo sample gained, lost, or changed no file."""
    before = world.state["sample_snapshot"]
    after = _snapshot(world.state["sample_root"])
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(
        name
        for name in set(before) & set(after)
        if before[name] != after[name]
    )
    assert not (added or removed or changed), (
        f"todo sample changed: added={added} removed={removed} changed={changed}"
    )


HANDLERS = [
    (r"^the harness pack holds its own config and the todo config$", _pack_configs),
    (r"^wiring is loaded through the (.+) config$", _load_through_config),
    (r"^the resolved workspace is the <workspace>$", _resolved_workspace),
    (
        r"^a temporary project whose config places its persistent root in the (.+)$",
        _project_with_persistent_location,
    ),
    (r"^the wired config is loaded$", _load_wired_config),
    (r"^the selected persistent root is inside the (.+)$", _selected_inside),
    (r"^the todo sample wired through the pack todo config$", _todo_wired),
    (r"^the todo config is resolved$", _todo_resolved),
    (r"^the resolved (.+) path is inside the harness pack$", _resolved_area_in_pack),
    (r"^the todo sample acceptance pipeline runs$", _pipeline_runs),
    (r"^the todo sample acceptance pipeline passes$", _pipeline_passes),
    (r"^the todo sample is snapshotted$", _sample_snapshot),
    (r"^no file appears or changes under the todo sample$", _sample_unchanged),
]
