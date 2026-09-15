"""Shared helpers for the acceptance step handler modules."""

import atexit
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import wiring
from runtime import World

_TEMP_DIRS: list[Path] = []

TEAM = "team.py"
TOOLS = Path(__file__).resolve().parents[4] / "tools"


def step_values(examples: dict[str, str], pattern: str) -> tuple:
    """Extract quoted values from the step text, resolving ``<name>`` placeholders."""
    text = examples.get("_step_text", "")
    match = re.match(pattern, text)
    assert match, f"step text did not match: {text!r}"

    def _sub(found: re.Match[str]) -> str:
        name = found.group(1)
        assert name in examples, f"missing example value for <{name}>"
        return examples[name]

    values = []
    for raw in match.groups():
        if raw is None:
            values.append(None)
        else:
            values.append(re.sub(r"<([A-Za-z0-9_]+)>", _sub, raw))
    return tuple(values)


def assert_refused(result: subprocess.CompletedProcess, problem: str, what: str) -> None:
    """Assert a tool run refused with exit 2 and stderr naming ``problem``."""
    assert result.returncode == 2, f"{what} was not refused: {result.stdout}"
    assert problem in result.stderr, result.stderr


def _cleanup_temp_dirs() -> None:
    while _TEMP_DIRS:
        shutil.rmtree(_TEMP_DIRS.pop(), ignore_errors=True)


atexit.register(_cleanup_temp_dirs)


def _temp_root() -> Path:
    root = Path(tempfile.mkdtemp(prefix="swarm-wiring-"))
    _TEMP_DIRS.append(root)
    return root


def _temp_harness(world: World) -> Path:
    """Install a temp harness config with absent roots and return its root."""
    os.environ.pop("SWARM_STATE_ROOT", None)
    wiring.clear_cache()
    root = _temp_root()
    world.state["project"] = root
    world.state["config"] = _write_absent_config(root)
    world.state["state_root"] = root / "real-state"
    return root


def _write_absent_config(root: Path) -> Path:
    """Write the shared temp harness config whose project roots are absent."""
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
    return config


def _project(world: World) -> Path:
    return world.state["project"]


def _state_root(world: World) -> Path:
    return world.state["state_root"]


def _tool_env(world: World) -> dict[str, str]:
    """Environment for a tool run: the temp project's config, no ambient SWARM_*."""
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("SWARM_")
    }
    env["SWARM_CONFIG"] = str(world.state["config"])
    return env


def _tool_argv(
    world: World, script: str, args, state_root: Path | None = None
) -> list[str]:
    """Build the argv for one harness CLI run in the temp project."""
    prefix = ["--root", str(_project(world))]
    if state_root is not None:
        prefix += ["--state-root", str(state_root)]
    return [sys.executable, str(TOOLS / script), *prefix, *args]


def _popen_tool(
    world: World, script: str, args, state_root: Path | None = None
) -> subprocess.Popen:
    """Start one harness CLI script as its own operating-system process."""
    return subprocess.Popen(
        _tool_argv(world, script, args, state_root),
        env=_tool_env(world),
        cwd=str(_project(world)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _collect(proc: subprocess.Popen) -> subprocess.CompletedProcess:
    """Wait for a started process and capture its output."""
    stdout, stderr = proc.communicate()
    return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)


def _run_tool(
    world: World, script: str, *args: str, state_root: Path | None = None
) -> subprocess.CompletedProcess:
    """Run one harness CLI script in the temp project and return the result."""
    return _collect(_popen_tool(world, script, args, state_root))


def _run_together(world: World, calls) -> list[subprocess.CompletedProcess]:
    """Run ``(script, args, state_root)`` calls as concurrent OS processes.

    Every process starts before any result is collected, so they contend on the
    same advisory lock. Returns one CompletedProcess per call in call order.
    """
    procs = [
        _popen_tool(world, script, args, state_root)
        for script, args, state_root in calls
    ]
    return [_collect(proc) for proc in procs]


def _run_team(world: World, *args: str) -> subprocess.CompletedProcess:
    """Run team.py CLI on the temp project and return the result."""
    return _run_tool(world, TEAM, *args)


def _run_harness(world: World, *args: str) -> subprocess.CompletedProcess:
    """Run the harness CLI in the temp project and return the result."""
    return subprocess.run(
        [sys.executable, str(TOOLS / "harness"), *args],
        env=_tool_env(world),
        cwd=str(_project(world)),
        capture_output=True,
        text=True,
    )


def _task_dir(world: World, task: str) -> Path:
    """Return the live task folder under tasks/<date>/<task>."""
    state = _state_root(world)
    today = world.state.get("open_date", "unknown")
    return state / "tasks" / today / task


def _task_json(world: World) -> Path:
    """Return the current task's ``task.json`` path."""
    return _task_dir(world, world.state["task"]) / "task.json"


def _done_dir(world: World, task: str) -> Path:
    """Return the preserved task folder under done/<date>/<task>."""
    state = _state_root(world)
    today = world.state.get("open_date", "unknown")
    return state / "done" / today / task


def _only_dir(parent: Path, what: str = "chunk dir") -> Path:
    """Return the single subdirectory of ``parent``; assert exactly one."""
    dirs = [child for child in parent.iterdir() if child.is_dir()]
    assert len(dirs) == 1, f"expected one {what} under {parent}, got {dirs}"
    return dirs[0]


def _section_body(payload: str, headers, header: str) -> str:
    """Return the lines after ``header`` up to the next known header."""
    lines = payload.splitlines()
    start = lines.index(header) + 1
    body = []
    for line in lines[start:]:
        if line.strip() in headers:
            break
        body.append(line)
    return "\n".join(body)


def _journal_text(chunk: Path) -> str:
    """Return a chunk's raw journal text."""
    return (chunk / "journal.jsonl").read_text()


def _journal_lines(chunk: Path) -> list[str]:
    """Return the non-blank lines of a chunk's journal."""
    return [line for line in _journal_text(chunk).splitlines() if line.strip()]


def _run_coder_team(world: World, *args: str) -> subprocess.CompletedProcess:
    """Run team.py on the temp project, keeping real state off the config paths."""
    return _run_tool(world, TEAM, *args, state_root=world.state["state_root"])
