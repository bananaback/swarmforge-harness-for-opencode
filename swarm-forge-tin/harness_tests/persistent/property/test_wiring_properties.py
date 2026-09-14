import json
from pathlib import Path

import pytest
import wiring
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

FRAGMENTS = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_-", min_size=1, max_size=16)
SETTINGS = settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@pytest.fixture(autouse=True)
def _clear_cache():
    wiring.clear_cache()
    yield
    wiring.clear_cache()


def write_pack(tmp_path, **fields):
    pack = tmp_path / "pack"
    (pack / "tools").mkdir(parents=True, exist_ok=True)
    (pack / "tools" / "wiring.py").write_text("")
    config = pack / "harness.json"
    config.write_text(json.dumps({"version": 1, **fields}))
    return config


@SETTINGS
@given(fragment=FRAGMENTS)
def test_state_override_is_absolute_and_stable(tmp_path, fragment):
    override = str(tmp_path / fragment)
    first = wiring.state_root_for(tmp_path, override=override)
    second = wiring.state_root_for(tmp_path, override=override)
    assert first.is_absolute()
    assert first == second
    assert first == (tmp_path / fragment).resolve()


@SETTINGS
@given(fragment=FRAGMENTS)
def test_env_hot_override_wins(tmp_path, monkeypatch, fragment):
    config = write_pack(tmp_path, workspace_root="..", hot_tests="hot")
    monkeypatch.setenv("SWARM_CONFIG", str(config))
    monkeypatch.setenv("SWARM_HOT", str(tmp_path / fragment))
    wiring.clear_cache()
    resolved = wiring.load()
    assert resolved.hot_tests == (tmp_path / fragment).resolve()


@SETTINGS
@given(workspace=FRAGMENTS, hot=FRAGMENTS, state=FRAGMENTS)
def test_relative_config_paths_resolve_absolute(tmp_path, workspace, hot, state):
    config = write_pack(
        tmp_path,
        workspace_root=workspace,
        hot_tests=hot,
        state_root=state,
        artifacts_root=hot,
        source_roots=[workspace],
    )
    wiring.clear_cache()
    data = wiring.load(config=config).as_dict()
    for key in (
        "pack_root",
        "workspace_root",
        "state_root",
        "artifacts_root",
        "hot_tests",
    ):
        assert Path(data[key]).is_absolute()


@SETTINGS
@given(parts=st.lists(FRAGMENTS, min_size=1, max_size=3))
def test_persistent_pythonpath_resolves_under_root(tmp_path, parts):
    entry = {"root": "tests", "pythonpath": parts, "kind": "project"}
    config = write_pack(tmp_path, persistent_tests=[entry])
    wiring.clear_cache()
    recorded = wiring.load(config=config).persistent_tests[0]
    root = recorded["root"]
    assert root.is_absolute()
    assert len(recorded["pythonpath"]) == len(parts)
    for path in recorded["pythonpath"]:
        assert path.is_absolute()
        assert path.is_relative_to(root)
