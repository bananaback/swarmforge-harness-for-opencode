import importlib.util
import os
from importlib.machinery import SourceFileLoader
from pathlib import Path

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
