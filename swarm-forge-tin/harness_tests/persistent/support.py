"""Shared helpers for harness tests."""

import json
import os
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"


def env_without_swarm(**extra):
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("SWARM_")
    }
    env.update({key: str(value) for key, value in extra.items()})
    return env


def project_config(tmp_path, name="project", **fields):
    """Create a temp project with a harness config; return (project, config)."""
    project = tmp_path / name
    project.mkdir(parents=True, exist_ok=True)
    config = project / "harness.json"
    config.write_text(
        json.dumps(
            {"version": 1, "workspace_root": ".", "state_root": "state", **fields}
        )
    )
    return project, config


def run_tool(script, project, config, *args, state_root=None):
    """Run a harness CLI in the temp project with its config pinned.

    ``state_root`` is an optional global override so a test can keep real state
    somewhere writable while the pinned config reports another location.
    """
    prefix = ["--root", str(project)]
    if state_root is not None:
        prefix += ["--state-root", str(state_root)]
    return subprocess.run(
        [sys.executable, str(TOOLS / script), *prefix, *args],
        env=env_without_swarm(SWARM_CONFIG=config),
        cwd=str(project),
        capture_output=True,
        text=True,
    )
