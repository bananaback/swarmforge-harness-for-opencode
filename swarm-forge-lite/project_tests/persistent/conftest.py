"""Make the project source importable for the persistent tests."""

import sys
from pathlib import Path

_PACK_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_ROOT = _PACK_ROOT / "tools" / "shared"
if str(_TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(_TOOLS_ROOT))

import wiring  # noqa: E402

_WORKSPACE_ROOT = wiring.load(environ={}).workspace_root
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))
