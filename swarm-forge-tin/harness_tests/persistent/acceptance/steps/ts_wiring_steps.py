"""Step handlers for the TS wiring acceptance feature.

The feature pins the opencode TypeScript resolver (``.opencode/lib/wiring.ts``)
to the Python resolver's order. Each resolving step shells out to Node with the
same loader the TS unit suite uses, runs the no-start probe, and reads back the
config path it printed.
"""

import os
import shutil
import subprocess
from pathlib import Path

import wiring
from runtime import World

from .common import TOOLS, _project, _temp_root

WORKSPACE = TOOLS.parent.parent
TS_DIR = Path(__file__).resolve().parents[2] / "tools" / "ts"
LOADER = TS_DIR / "ts-resolve.mjs"
PROBE = Path(__file__).resolve().parents[1] / "ts_config_probe.mjs"
WIRING_TS = WORKSPACE / ".opencode" / "lib" / "wiring.ts"
NODE = shutil.which("node")


def _nested_working_directory(world: World, examples: dict[str, str]) -> None:
    """And a nested working directory under that project."""
    nested = _project(world) / "a" / "b"
    nested.mkdir(parents=True, exist_ok=True)
    world.state["working_dir"] = nested


def _neutral_working_directory(world: World, examples: dict[str, str]) -> None:
    """Given a working directory with no harness config above it."""
    root = _temp_root()
    world.state["project"] = root
    world.state["working_dir"] = root


def _node_env() -> dict[str, str]:
    """Environment for the probe: no SWARM_* overrides, the resolver path set."""
    env = {
        key: value for key, value in os.environ.items() if not key.startswith("SWARM_")
    }
    env["SWARM_TS_WIRING"] = str(WIRING_TS)
    return env


def _resolve_ts_config(world: World) -> None:
    assert NODE, "node is required to resolve the TS config"
    result = subprocess.run(
        [
            NODE,
            "--disable-warning=MODULE_TYPELESS_PACKAGE_JSON",
            "--import",
            str(LOADER),
            str(PROBE),
        ],
        cwd=str(world.state["working_dir"]),
        env=_node_env(),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"TS resolver failed: {result.stderr}"
    world.state["ts_config"] = Path(result.stdout.strip())


def _resolved_with_no_start(world: World, examples: dict[str, str]) -> None:
    """When the TS config is resolved with no start (nested or neutral cwd)."""
    _resolve_ts_config(world)


def _reports_project_config(world: World, examples: dict[str, str]) -> None:
    """Then the TS resolver reports the project config."""
    expected = world.state["config"].resolve()
    assert world.state["ts_config"] == expected, (
        f"TS resolver reported {world.state['ts_config']}, expected {expected}"
    )


def _reports_pack_config(world: World, examples: dict[str, str]) -> None:
    """Then the TS resolver reports the harness pack config."""
    expected = (wiring.PACK_ROOT / "harness.json").resolve()
    assert world.state["ts_config"] == expected, (
        f"TS resolver reported {world.state['ts_config']}, expected {expected}"
    )


HANDLERS = [
    (r"^a nested working directory under that project$", _nested_working_directory),
    (
        r"^a working directory with no harness config above it$",
        _neutral_working_directory,
    ),
    (
        r"^the TS config is resolved with no start from the nested working directory$",
        _resolved_with_no_start,
    ),
    (r"^the TS config is resolved with no start$", _resolved_with_no_start),
    (r"^the TS resolver reports the project config$", _reports_project_config),
    (r"^the TS resolver reports the harness pack config$", _reports_pack_config),
]
