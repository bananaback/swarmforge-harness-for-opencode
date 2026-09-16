import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

_dump_dir = Path(__file__).resolve().parent.parent / "dump"
os.environ.setdefault(
    "HYPOTHESIS_STORAGE_DIRECTORY", str(_dump_dir / "hypothesis-project")
)
