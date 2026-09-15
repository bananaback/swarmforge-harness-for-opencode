import importlib.util
import json
import os
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

TOOLS = Path(__file__).resolve().parents[2].parent / "tools"


def load_tool(name):
    loader = SourceFileLoader(name, str(TOOLS / name))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_display_path_accepts_missing_prefix():
    dry4py = load_tool("dry4py")
    assert dry4py.display_path(None, "src/a.py") == "src/a.py"
    assert dry4py.display_path("", "src/a.py") == "src/a.py"
    assert dry4py.display_path(".", "src/a.py") == "src/a.py"
    assert dry4py.display_path("src", "a.py") == os.path.join("src", "a.py")


def test_display_path_keeps_absolute_and_prefixed_names():
    dry4py = load_tool("dry4py")
    assert dry4py.display_path("src", "/abs/a.py") == "/abs/a.py"
    assert dry4py.display_path("src", "src/a.py") == "src/a.py"


def _write_report(path, duplicates=(), total=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"duplicates": list(duplicates), "statistics": {"total": total or {}}}
        )
    )


def _resolved(tmp_path):
    source = tmp_path / "src"
    source.mkdir(exist_ok=True)
    return SimpleNamespace(
        artifacts_root=tmp_path / "dump",
        source_roots=[source],
    )


def _fake_run(returncode=0):
    return lambda command: SimpleNamespace(returncode=returncode)


def test_main_reports_no_duplicates(tmp_path, monkeypatch):
    dry4py = load_tool("dry4py")
    resolved = _resolved(tmp_path)
    _write_report(resolved.artifacts_root / "dry4py" / "jscpd-report.json")
    monkeypatch.setattr(dry4py.wiring, "load", lambda: resolved)
    monkeypatch.setattr(dry4py.shutil, "which", lambda name: "/usr/bin/jscpd")
    monkeypatch.setattr(dry4py.subprocess, "run", _fake_run())
    assert dry4py.main([str(resolved.source_roots[0])]) == 0


def test_main_reports_duplicates_and_honours_fail_on_duplicates(tmp_path, monkeypatch):
    dry4py = load_tool("dry4py")
    resolved = _resolved(tmp_path)
    _write_report(
        resolved.artifacts_root / "dry4py" / "jscpd-report.json",
        duplicates=[
            {
                "lines": 4,
                "tokens": 20,
                "firstFile": {"name": "a.py", "start": 1, "end": 4},
                "secondFile": {"name": "b.py", "start": 5, "end": 8},
            }
        ],
        total={"duplicatedLines": 4, "percentage": 1.5},
    )
    monkeypatch.setattr(dry4py.wiring, "load", lambda: resolved)
    monkeypatch.setattr(dry4py.shutil, "which", lambda name: "/usr/bin/jscpd")
    monkeypatch.setattr(dry4py.subprocess, "run", _fake_run())
    assert dry4py.main(["--fail-on-duplicates", str(resolved.source_roots[0])]) == 2


def test_main_copies_an_explicit_report(tmp_path, monkeypatch):
    dry4py = load_tool("dry4py")
    resolved = _resolved(tmp_path)
    _write_report(tmp_path / "jscpd-report.json")
    explicit = tmp_path / "explicit.json"
    monkeypatch.setattr(dry4py.wiring, "load", lambda: resolved)
    monkeypatch.setattr(dry4py.shutil, "which", lambda name: "/usr/bin/jscpd")
    monkeypatch.setattr(dry4py.subprocess, "run", _fake_run())
    assert dry4py.main(["--report", str(explicit), str(resolved.source_roots[0])]) == 0
    assert explicit.exists()


def test_main_reports_a_missing_jscpd(tmp_path, monkeypatch):
    dry4py = load_tool("dry4py")
    resolved = SimpleNamespace(artifacts_root=tmp_path / "dump", source_roots=[])
    monkeypatch.setattr(dry4py.wiring, "load", lambda: resolved)
    monkeypatch.setattr(dry4py.shutil, "which", lambda name: None)
    assert dry4py.main([]) == 1


def test_main_reports_a_jscpd_failure(tmp_path, monkeypatch):
    dry4py = load_tool("dry4py")
    resolved = _resolved(tmp_path)
    monkeypatch.setattr(dry4py.wiring, "load", lambda: resolved)
    monkeypatch.setattr(dry4py.shutil, "which", lambda name: "/usr/bin/jscpd")
    monkeypatch.setattr(dry4py.subprocess, "run", _fake_run(returncode=2))
    assert dry4py.main([str(resolved.source_roots[0])]) == 1


def test_main_reports_a_missing_report(tmp_path, monkeypatch):
    dry4py = load_tool("dry4py")
    resolved = _resolved(tmp_path)
    monkeypatch.setattr(dry4py.wiring, "load", lambda: resolved)
    monkeypatch.setattr(dry4py.shutil, "which", lambda name: "/usr/bin/jscpd")
    monkeypatch.setattr(dry4py.subprocess, "run", _fake_run())
    assert dry4py.main([str(resolved.source_roots[0])]) == 1


def test_clone_prefix_only_names_a_single_directory(tmp_path):
    dry4py = load_tool("dry4py")
    first = tmp_path / "a"
    second = tmp_path / "b"
    first.mkdir()
    second.mkdir()
    assert dry4py._clone_prefix([str(first)]) == str(first)
    assert dry4py._clone_prefix([str(first), str(second)]) is None
    assert dry4py._clone_prefix([str(tmp_path / "file.py")]) is None

