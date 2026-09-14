import json
import subprocess
import sys
from pathlib import Path

import pytest
import wiring
from support import env_without_swarm

TOOLS = Path(__file__).resolve().parents[2].parent / "tools"
HARNESS = TOOLS / "harness"


def write_config(directory, **fields):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "tools").mkdir(exist_ok=True)
    (directory / "tools" / "wiring.py").write_text("")
    config = directory / "harness.json"
    config.write_text(json.dumps({"version": 1, **fields}))
    return config


def run_harness(args, config, cwd):
    env = env_without_swarm(SWARM_CONFIG=config)
    return subprocess.run(
        [sys.executable, str(HARNESS), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    for name in (
        "SWARM_CONFIG",
        "SWARM_PACK",
        "SWARM_WORKSPACE",
        "SWARM_STATE_ROOT",
        "SWARM_HOT",
    ):
        monkeypatch.delenv(name, raising=False)
    wiring.clear_cache()
    yield
    wiring.clear_cache()


def test_load_resolves_relative_paths(tmp_path):
    config = write_config(
        tmp_path / "pack",
        workspace_root="..",
        state_root=".state",
        artifacts_root="out",
        hot_tests="hot",
        persistent_tests=[
            {"root": "tests", "pythonpath": ["src"], "kind": "project"}
        ],
        source_roots=["src"],
    )
    resolved = wiring.load(config=config)
    assert resolved.pack_root == (tmp_path / "pack").resolve()
    assert resolved.workspace_root == tmp_path.resolve()
    assert resolved.state_root == (tmp_path / "pack" / ".state").resolve()
    assert resolved.artifacts_root == (tmp_path / "pack" / "out").resolve()
    assert resolved.hot_tests == (tmp_path / "pack" / "hot").resolve()
    entry = resolved.persistent_tests[0]
    assert entry["root"] == (tmp_path / "pack" / "tests").resolve()
    assert entry["pythonpath"] == ((tmp_path / "pack" / "tests" / "src").resolve(),)
    assert resolved.source_roots == ((tmp_path / "pack" / "src").resolve(),)


def test_finds_config_upward(tmp_path):
    config = write_config(tmp_path / "proj", workspace_root=".")
    nested = tmp_path / "proj" / "a" / "b"
    nested.mkdir(parents=True)
    resolved = wiring.load(start=nested)
    assert resolved.config_path == config.resolve()


def test_env_config_and_state_overrides(tmp_path, monkeypatch):
    config = write_config(tmp_path / "pack", state_root=".state")
    monkeypatch.setenv("SWARM_CONFIG", str(config))
    monkeypatch.setenv("SWARM_STATE_ROOT", str(tmp_path / "elsewhere"))
    resolved = wiring.load()
    assert resolved.config_path == config.resolve()
    assert resolved.state_root == (tmp_path / "elsewhere").resolve()


def test_defaults_without_config(tmp_path, monkeypatch):
    pack = tmp_path / "pack"
    (pack / "tools").mkdir(parents=True)
    monkeypatch.setattr(wiring, "PACK_ROOT", pack)
    monkeypatch.setattr(wiring, "find_config", lambda start=None: None)
    resolved = wiring.load(start=tmp_path / "work")
    assert resolved.workspace_root == pack.parent.resolve()
    assert resolved.state_root == (pack.parent / "swarm-forge-tin" / ".swarmforge").resolve()
    assert resolved.artifacts_root == (pack / "dump").resolve()
    assert resolved.hot_tests == (pack / "hot_tests").resolve()


def test_state_root_for_override(tmp_path):
    resolved = wiring.state_root_for(tmp_path, override=str(tmp_path / "custom"))
    assert resolved == (tmp_path / "custom").resolve()


def test_state_root_for_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("SWARM_STATE_ROOT", str(tmp_path / "env-state"))
    assert wiring.state_root_for(tmp_path) == (tmp_path / "env-state").resolve()


def test_cli_config_prints_resolved_paths(tmp_path):
    config = write_config(tmp_path / "pack", workspace_root="..", hot_tests="hot")
    result = run_harness(["config"], config, tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["pack_root"] == str((tmp_path / "pack").resolve())
    assert payload["workspace_root"] == str(tmp_path.resolve())


def test_cli_clean_hot_clears_contents(tmp_path):
    hot = tmp_path / "pack" / "hot"
    (hot / "acceptance").mkdir(parents=True)
    (hot / "acceptance" / "test_generated.py").write_text("")
    config = write_config(tmp_path / "pack", hot_tests="hot")
    result = run_harness(["clean", "hot"], config, tmp_path)
    assert result.returncode == 0, result.stderr
    assert hot.is_dir()
    assert list(hot.iterdir()) == []


def test_cli_clean_artifacts_clears_contents(tmp_path):
    artifacts = tmp_path / "pack" / "out"
    (artifacts / "dry4py").mkdir(parents=True)
    (artifacts / "coverage.lcov").write_text("")
    config = write_config(tmp_path / "pack", artifacts_root="out")
    result = run_harness(["clean", "artifacts"], config, tmp_path)
    assert result.returncode == 0, result.stderr
    assert list(artifacts.iterdir()) == []


def test_cli_clean_state_refuses_in_process(tmp_path):
    state = tmp_path / "pack" / ".state"
    inbox = state / "mail" / "inbox" / "coder" / "in_process"
    inbox.mkdir(parents=True)
    (inbox / "01_item.json").write_text("{}")
    config = write_config(tmp_path / "pack", state_root=".state")
    refused = run_harness(["clean", "state"], config, tmp_path)
    assert refused.returncode == 2
    assert (inbox / "01_item.json").exists()
    forced = run_harness(["clean", "state", "--force"], config, tmp_path)
    assert forced.returncode == 0, forced.stderr
    assert not (inbox / "01_item.json").exists()


def test_cli_clean_state_refuses_held_team_seat(tmp_path):
    state = tmp_path / "pack" / ".state"
    held = state / "team" / "c1" / "seats" / "worker" / "in_process"
    held.mkdir(parents=True)
    (held / "01_item.json").write_text("{}")
    config = write_config(tmp_path / "pack", state_root=".state")
    refused = run_harness(["clean", "state"], config, tmp_path)
    assert refused.returncode == 2
    assert "in-process item(s)" in refused.stderr
    assert (held / "01_item.json").exists()
    forced = run_harness(["clean", "state", "--force"], config, tmp_path)
    assert forced.returncode == 0, forced.stderr
    assert not (held / "01_item.json").exists()


def test_env_workspace_and_hot_overrides(tmp_path, monkeypatch):
    config = write_config(tmp_path / "pack", workspace_root="..", hot_tests="hot")
    monkeypatch.setenv("SWARM_CONFIG", str(config))
    monkeypatch.setenv("SWARM_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("SWARM_HOT", str(tmp_path / "hot-elsewhere"))
    resolved = wiring.load()
    assert resolved.workspace_root == (tmp_path / "ws").resolve()
    assert resolved.hot_tests == (tmp_path / "hot-elsewhere").resolve()


def test_invalid_config_raises(tmp_path):
    bad = tmp_path / "harness.json"
    bad.write_text("{not json")
    with pytest.raises(wiring.WiringError):
        wiring.load(config=bad)


def test_missing_explicit_config_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("SWARM_CONFIG", str(tmp_path / "missing.json"))
    with pytest.raises(wiring.WiringError):
        wiring.load()


def test_swarm_pack_env_resolves_pack(tmp_path, monkeypatch):
    pack = tmp_path / "pack"
    write_config(pack, workspace_root="..")
    neutral = tmp_path / "neutral"
    neutral.mkdir()
    monkeypatch.setenv("SWARM_PACK", str(pack))
    resolved = wiring.load(start=neutral)
    assert resolved.pack_root == pack.resolve()
    assert resolved.config_path == (pack / "harness.json").resolve()


def test_invalid_persistent_entry_raises(tmp_path):
    config = write_config(tmp_path / "pack", persistent_tests=[{"pythonpath": []}])
    with pytest.raises(wiring.WiringError):
        wiring.load(config=config)


def test_cli_clean_all_clears_shared_areas(tmp_path):
    pack = tmp_path / "pack"
    (pack / "hot" / "acceptance").mkdir(parents=True)
    (pack / "hot" / "acceptance" / "test_gen.py").write_text("")
    (pack / "out" / "dry4py").mkdir(parents=True)
    (pack / "out" / "coverage.lcov").write_text("")
    completed = pack / "state" / "mail" / "inbox" / "coder" / "completed"
    completed.mkdir(parents=True)
    (completed / "01_done.json").write_text("{}")
    config = write_config(
        pack, hot_tests="hot", artifacts_root="out", state_root="state"
    )
    result = run_harness(["clean", "all"], config, tmp_path)
    assert result.returncode == 0, result.stderr
    assert list((pack / "hot").iterdir()) == []
    assert list((pack / "out").iterdir()) == []
    assert list((pack / "state").iterdir()) == []
