import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

os.environ.setdefault(
    "HYPOTHESIS_STORAGE_DIRECTORY",
    str(Path(__file__).resolve().parent.parent / "dump" / "hypothesis"),
)
