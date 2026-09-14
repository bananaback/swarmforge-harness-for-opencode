"""Step handlers for the harness wiring acceptance feature."""

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import wiring
from runtime import World

_TEMP_DIRS: list[Path] = []


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


STEP_HANDLERS = [
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
]
