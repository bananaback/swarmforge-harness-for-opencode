"""In-process unit tests for the extensionless ``tools/harness`` script.

The subprocess suite pins the CLI contract; loading the script as a module lets
coverage and CRAP measure its helpers, in particular ``_in_process_count`` and
the ``status``/``clean`` command bodies.
"""

import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest
import wiring
from support import project_config

TOOLS = Path(__file__).resolve().parents[2].parent / "tools"


@pytest.fixture(autouse=True)
def _no_swarm_env(monkeypatch):
    for name in ("SWARM_PACK", "SWARM_WORKSPACE", "SWARM_STATE_ROOT", "SWARM_HOT"):
        monkeypatch.delenv(name, raising=False)
    wiring.clear_cache()


def load_harness():
    loader = SourceFileLoader("harness_tool", str(TOOLS / "harness"))
    spec = importlib.util.spec_from_loader("harness_tool", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture
def clean_pack(tmp_path):
    """A pack whose managed roots exist, wired for the clean-command tests."""
    pack, config = project_config(
        tmp_path, "pack", state_root=".state", artifacts_root="dump", hot_tests="hot"
    )
    (pack / "hot").mkdir(parents=True)
    (pack / "dump").mkdir(parents=True)
    return pack, config


def test_in_process_count_counts_mail_and_live_tasks(tmp_path):
    harness = load_harness()
    state = tmp_path / "state"

    # No state at all: neither root exists.
    assert harness._in_process_count(state) == 0

    inbox = state / "mail" / "inbox" / "worker" / "in_process"
    inbox.mkdir(parents=True)
    (inbox / "01_item.json").write_text("{}")
    assert harness._in_process_count(state) == 1

    task = state / "tasks" / "2026-09-14" / "feature" / "periods"
    task.mkdir(parents=True)
    (task / "task.json").write_text("{}")
    assert harness._in_process_count(state) == 2


def test_clean_dir_removes_files_dirs_and_symlinks(tmp_path):
    harness = load_harness()
    target = tmp_path / "hot"
    target.mkdir()
    (target / "file.txt").write_text("x")
    nested = target / "nested"
    nested.mkdir()
    (nested / "inner.txt").write_text("y")
    real = tmp_path / "real"
    real.mkdir()
    (target / "link").symlink_to(real, target_is_directory=True)

    assert harness._clean_dir(target) == 3
    assert list(target.iterdir()) == []
    assert real.is_dir()

    # A missing directory is created and reports nothing removed.
    fresh = tmp_path / "fresh"
    assert harness._clean_dir(fresh) == 0
    assert fresh.is_dir()


def test_status_prints_rows_and_persistent_roots(tmp_path, capsys):
    harness = load_harness()
    pack, config = project_config(
        tmp_path,
        "pack",
        state_root=".state",
        artifacts_root="dump",
        hot_tests="hot",
        persistent_tests=[
            {"root": "harness_tests", "kind": "harness"},
            {"root": "absent", "kind": "project"},
        ],
    )
    (pack / "harness_tests").mkdir(parents=True)

    assert harness.main(["--config", str(config), "status"]) == 0
    out = capsys.readouterr().out
    assert "PACK       [ok]" in out
    assert "PERSIST    [ok]" in out
    assert "PERSIST    [-]" in out


def test_clean_targets_remove_the_right_root(clean_pack, capsys):
    harness = load_harness()
    pack, config = clean_pack
    hot = pack / "hot"
    (hot / "x.txt").write_text("x")
    artifacts = pack / "dump"
    (artifacts / "y.txt").write_text("y")
    state = pack / ".state"
    state.mkdir(parents=True)
    (state / "z.txt").write_text("z")

    assert harness.main(["--config", str(config), "clean", "hot"]) == 0
    assert not list(hot.iterdir())
    assert harness.main(["--config", str(config), "clean", "artifacts"]) == 0
    assert not list(artifacts.iterdir())
    assert harness.main(["--config", str(config), "clean", "state"]) == 0
    assert not list(state.iterdir())
    assert harness.main(["--config", str(config), "clean", "all"]) == 0
    capsys.readouterr()


def test_clean_state_refuses_while_items_are_in_process(clean_pack, capsys):
    harness = load_harness()
    pack, config = clean_pack
    inbox = pack / ".state" / "mail" / "inbox" / "worker" / "in_process"
    inbox.mkdir(parents=True)
    (inbox / "01_item.json").write_text("{}")

    assert harness.main(["--config", str(config), "clean", "state"]) == 2
    assert "in-process item(s)" in capsys.readouterr().err
    assert (inbox / "01_item.json").exists()

    assert harness.main(["--config", str(config), "clean", "state", "--force"]) == 0
    assert not (inbox / "01_item.json").exists()
    capsys.readouterr()


def test_clean_with_no_target_defaults_to_hot(clean_pack, capsys):
    harness = load_harness()
    pack, config = clean_pack
    hot = pack / "hot"
    (hot / "x.txt").write_text("x")
    artifacts = pack / "dump"
    (artifacts / "y.txt").write_text("y")

    assert harness.main(["--config", str(config), "clean"]) == 0
    assert not list(hot.iterdir())
    assert (artifacts / "y.txt").is_file()
    capsys.readouterr()
