"""Automated checks for the opencode TS bridges.

`.opencode/lib/wiring.ts` and `.opencode/lib/team-autobind.ts` run under
opencode's Bun runtime. These tests execute the same sources under Node (native
type stripping plus the `ts/ts-resolve.mjs` hook) so the resolver's behavior is
pinned and the auto-bind hook is probed end to end without a full opencode
spawn.

The probe opens a real phase chunk with `tools/team.py`, proves an unbound
session cannot pull, runs the real `autoBindPendingSeat` logic, and proves the
session is bound (status `queued`, pull `RESUMED`) before its first pull.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from support import TOOLS, env_without_swarm, project_config, run_tool

WORKSPACE = TOOLS.parent.parent
TS_DIR = Path(__file__).resolve().parent / "ts"
LOADER = TS_DIR / "ts-resolve.mjs"
SUITE = TS_DIR / "wiring.test.ts"
PROBE = TS_DIR / "autobind_probe.ts"
LIB_DIR = WORKSPACE / ".opencode" / "lib"
REAL_PACK = WORKSPACE / "swarm-forge-tin"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is required for the TS bridge tests")


def node_env(**extra):
    env = env_without_swarm(**extra)
    env["SWARM_TS_LIB"] = str(LIB_DIR)
    env["SWARM_PACK"] = str(REAL_PACK)
    return env


def run_node(*args, env=None):
    return subprocess.run(
        [NODE, "--disable-warning=MODULE_TYPELESS_PACKAGE_JSON", "--import", str(LOADER), *args],
        cwd=str(TS_DIR),
        env=env or node_env(),
        capture_output=True,
        text=True,
    )


def team(project, config, *args):
    return run_tool("team.py", project, config, *args)


def test_ts_resolver_suite_passes():
    result = run_node("--test", str(SUITE))
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    assert "fail 0" in result.stdout


def test_autobind_binds_before_the_first_pull(tmp_path):
    project, config = project_config(tmp_path)
    opened = team(project, config, "open", "c1", "--role", "coder")
    assert opened.returncode == 0, opened.stderr

    pending = team(project, config, "status", "--ready")
    assert "READY: c1 worker SPAWN_PENDING" in pending.stdout

    # Without the bind, the pull is refused: autobind is what makes it resolve.
    unbound = team(project, config, "pull", "--session", "s-coder-probe")
    assert unbound.returncode == 2
    assert "not bound" in unbound.stderr

    probe = run_node(
        str(PROBE),
        str(project),
        "s-coder-probe",
        "coder",
        env=node_env(SWARM_CONFIG=str(config)),
    )
    assert probe.returncode == 0, probe.stderr
    payload = json.loads(probe.stdout.strip().splitlines()[-1])
    assert payload["bound"] is True, payload
    assert "worker" in payload["reason"]

    # Bound on the wake, before the child's first pull.
    bound = team(project, config, "status", "--ready")
    assert "READY: c1 worker queued" in bound.stdout

    resumed = team(project, config, "pull", "--session", "s-coder-probe")
    assert resumed.returncode == 0, resumed.stderr
    assert "RESUMED: yes" in resumed.stdout
