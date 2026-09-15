"""Step handlers for the harness wiring acceptance feature."""

import json
import os
from pathlib import Path

import wiring
from runtime import World

from .common import _project, _temp_root, step_values


def _pack(world: World) -> Path:
    return world.state["pack"]


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
    world.state["config"] = root / "harness.json"
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


def _env_override(world: World, examples: dict[str, str]) -> None:
    (variable,) = step_values(
        examples, r"^the environment sets the (\S+) to an override directory$"
    )
    override = _project(world) / "override"
    os.environ[variable] = str(override)
    world.state["override"] = override
    world.state["override_variable"] = variable


def _drop_override(world: World) -> None:
    variable = world.state.get("override_variable")
    if variable:
        os.environ.pop(variable, None)


def _env_override_reported(world: World, examples: dict[str, str]) -> None:
    wiring.clear_cache()
    resolved = wiring.load(start=str(_project(world)))
    assert resolved.state_root == world.state["override"]
    _drop_override(world)


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


def _no_env_overrides(world: World, examples: dict[str, str]) -> None:
    for name in (
        "SWARM_CONFIG",
        "SWARM_PACK",
        "SWARM_WORKSPACE",
        "SWARM_STATE_ROOT",
        "SWARM_HOT",
    ):
        os.environ.pop(name, None)
    wiring.clear_cache()


def _env_config_missing(world: World, examples: dict[str, str]) -> None:
    os.environ["SWARM_CONFIG"] = str(_project(world) / "missing-harness.json")


def _neutral_directory(world: World, examples: dict[str, str]) -> None:
    world.state["project"] = _temp_root()


def _env_select_pack(world: World, examples: dict[str, str]) -> None:
    os.environ["SWARM_PACK"] = str(wiring.PACK_ROOT)
    world.state["pack"] = wiring.PACK_ROOT


def _load_from_directory(world: World, examples: dict[str, str]) -> None:
    wiring.clear_cache()
    world.state["resolved"] = wiring.load(start=str(_project(world)))


def _config_without_roots(world: World, examples: dict[str, str]) -> None:
    root = _temp_root()
    (root / "harness.json").write_text(json.dumps({"version": 1}))
    world.state["project"] = root
    world.state["pack"] = wiring.PACK_ROOT


def _artifacts_is_pack_dump(world: World, examples: dict[str, str]) -> None:
    assert _resolved(world).artifacts_root == _pack(world) / "dump"


def _roles_are_defaults(world: World, examples: dict[str, str]) -> None:
    assert _resolved(world).roles == wiring.DEFAULT_ROLES


def _env_workspace_reported(world: World, examples: dict[str, str]) -> None:
    wiring.clear_cache()
    resolved = wiring.load(start=str(_project(world)))
    assert resolved.workspace_root == world.state["override"]
    _drop_override(world)


def _env_hot_reported(world: World, examples: dict[str, str]) -> None:
    wiring.clear_cache()
    resolved = wiring.load(start=str(_project(world)))
    assert resolved.hot_tests == world.state["override"]
    _drop_override(world)


def _self_hosted_pack(world: World, examples: dict[str, str]) -> None:
    root = _temp_root()
    (root / "tools").mkdir(parents=True)
    (root / "tools" / "wiring.py").write_text("")
    config = {
        "version": 1,
        "workspace_root": ".",
        "persistent_tests": [
            {"root": "project-tests", "pythonpath": ["."], "kind": "project"},
            {"root": "harness-tests", "pythonpath": ["."], "kind": "harness"},
        ],
    }
    (root / "harness.json").write_text(json.dumps(config))
    world.state["pack"] = root
    world.state["project"] = root
    world.state["harness_root"] = root / "harness-tests"


def _wired_project(world: World, examples: dict[str, str]) -> None:
    root = _temp_root()
    config = {
        "version": 1,
        "workspace_root": ".",
        "persistent_tests": [
            {"root": "harness-tests", "pythonpath": ["."], "kind": "harness"},
            {"root": "project-tests", "pythonpath": ["."], "kind": "project"},
        ],
    }
    (root / "harness.json").write_text(json.dumps(config))
    world.state["project"] = root
    world.state["project_root"] = root / "project-tests"


def _select_persistent_root(world: World, examples: dict[str, str]) -> None:
    import team

    world.state["selected_persistent"] = team.persistent_test_root(_resolved(world))


def _selected_kind(world: World, examples: dict[str, str]) -> None:
    (kind,) = step_values(
        examples, r'^the selected persistent root has kind "([^"]*)"$'
    )
    selected = world.state["selected_persistent"]
    entries = _resolved(world).persistent_tests
    kinds = [entry["kind"] for entry in entries if entry["root"] == selected]
    assert kinds, f"selected root {selected} is not a configured persistent root"
    assert kinds[0] == kind, f"selected root kind is {kinds[0]!r}, expected {kind!r}"


HANDLERS = [
    (r"^no harness environment overrides$", _no_env_overrides),
    (r"^the harness pack$", _the_harness_pack),
    (r"^wiring is loaded from the (?:self-hosted )?pack$", _load_from_pack),
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
    (r"^the environment sets the (\S+) to an override directory$", _env_override),
    (r"^loading wiring reports the override directory as the state root$", _env_override_reported),
    (r"^the project persistent root still exists$", _persistent_still_exists),
    (r"^wiring is requested from that project$", _request_from_project),
    (r"^loading fails with a wiring error$", _loading_fails_with_wiring_error),
    (r"^the environment points the config at a missing file$", _env_config_missing),
    (r"^a temporary directory with no harness config$", _neutral_directory),
    (r"^the environment selects the harness pack$", _env_select_pack),
    (r"^wiring is loaded from that directory$", _load_from_directory),
    (r"^a temporary project with a config that sets no roots$", _config_without_roots),
    (r"^the resolved artifacts root is the pack dump directory$", _artifacts_is_pack_dump),
    (r"^the configured roles are the default roles$", _roles_are_defaults),
    (r"^the resolved workspace root is the override directory$", _env_workspace_reported),
    (r"^the resolved hot area is the override directory$", _env_hot_reported),
    (
        r"^a temporary self-hosted pack whose persistent roots are a project root "
        r"then a harness root$",
        _self_hosted_pack,
    ),
    (
        r"^a temporary wired project whose persistent roots are a harness root "
        r"then a project root$",
        _wired_project,
    ),
    (r"^the persistent test root is selected$", _select_persistent_root),
    (r'^the selected persistent root has kind "([^"]*)"$', _selected_kind),
]
