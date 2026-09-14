import json
import subprocess
import sys
from pathlib import Path

from support import env_without_swarm

TOOLS = Path(__file__).resolve().parents[2].parent / "tools"
MAILBOX = TOOLS / "mailbox.py"
TEAM = TOOLS / "team.py"


def config_for(project):
    project.mkdir(parents=True, exist_ok=True)
    config = project / "harness.json"
    config.write_text(
        json.dumps({"version": 1, "workspace_root": ".", "state_root": "state"})
    )
    return config


def run(script, project, config, *args):
    env = env_without_swarm(SWARM_CONFIG=config)
    return subprocess.run(
        [sys.executable, str(script), "--root", str(project), *args],
        env=env,
        cwd=str(project),
        capture_output=True,
        text=True,
    )


def test_mailbox_routes_state_from_config(tmp_path):
    project = tmp_path / "project"
    config = config_for(project)
    result = run(
        MAILBOX,
        project,
        config,
        "send",
        "--from",
        "orchestrator",
        "--to",
        "coder",
        "--task",
        "wiring",
        "--message",
        "pointer",
        "--session",
        "s1",
    )
    assert result.returncode == 0, result.stderr
    queued = project / "state" / "mail" / "inbox" / "coder" / "new"
    assert list(queued.glob("*.json"))


def test_team_routes_state_from_config(tmp_path):
    project = tmp_path / "project"
    config = config_for(project)
    result = run(TEAM, project, config, "open", "chunk-1", "--role", "coder", "--brief", "hello")
    assert result.returncode == 0, result.stderr
    import datetime
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    assert (project / "state" / "tasks" / today / "chunk-1" / "task.json").is_file()


def test_state_root_flag_overrides_config(tmp_path):
    project = tmp_path / "project"
    config = config_for(project)
    override = tmp_path / "elsewhere"
    env = env_without_swarm(SWARM_CONFIG=config)
    result = subprocess.run(
        [
            sys.executable,
            str(MAILBOX),
            "--root",
            str(project),
            "--state-root",
            str(override),
            "send",
            "--from",
            "orchestrator",
            "--to",
            "coder",
            "--task",
            "wiring",
            "--message",
            "pointer",
            "--session",
            "s1",
        ],
        env=env,
        cwd=str(project),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    queued = override / "mail" / "inbox" / "coder" / "new"
    assert list(queued.glob("*.json"))
