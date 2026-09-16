"""Focused tests for the harness portability step handlers.

The authored ``harness_portability`` feature is the proof: its IR is parsed with
the vendored ``gherkin-parser`` and run through a Runtime built from the wiring
handlers plus this module's handlers, so every scenario exercises the module's
own behavior end to end.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import wiring

ACCEPTANCE = Path(__file__).resolve().parents[1] / "acceptance"
sys.path.insert(0, str(ACCEPTANCE))

from runtime import Runtime, World  # noqa: E402
from steps import harness_portability_steps, wiring_steps  # noqa: E402

FEATURE = (
    wiring.PACK_ROOT
    / "harness_tests"
    / "persistent"
    / "features"
    / "harness_portability.feature"
)
PARSER = wiring.PACK_ROOT / "tools" / "gherkin-parser"

EXPECTED_PATTERNS = [
    r"^the harness pack holds its own config and the todo config$",
    r"^wiring is loaded through the (.+) config$",
    r"^the resolved workspace is the <workspace>$",
    r"^a temporary project whose config places its persistent root in the (.+)$",
    r"^the wired config is loaded$",
    r"^the selected persistent root is inside the (.+)$",
    r"^the todo sample wired through the pack todo config$",
    r"^the todo config is resolved$",
    r"^the resolved (.+) path is inside the harness pack$",
    r"^the todo sample acceptance pipeline runs$",
    r"^the todo sample acceptance pipeline passes$",
    r"^the todo sample is snapshotted$",
    r"^no file appears or changes under the todo sample$",
]


def _runtime() -> Runtime:
    runtime = Runtime()
    for pattern, handler in (
        *wiring_steps.HANDLERS,
        *harness_portability_steps.HANDLERS,
    ):
        runtime.register(pattern, handler)
    return runtime


def test_handlers_match_the_design_seed_table():
    patterns = [pattern for pattern, _handler in harness_portability_steps.HANDLERS]
    assert patterns == EXPECTED_PATTERNS


def test_harness_portability_feature_runs_through_its_handlers(tmp_path):
    assert FEATURE.is_file(), f"missing {FEATURE}"
    ir_file = tmp_path / f"{FEATURE.stem}.json"
    subprocess.run(
        [str(PARSER), str(FEATURE), str(ir_file)], check=True, capture_output=True
    )
    _runtime().run_all(json.loads(ir_file.read_text()))


def test_project_with_persistent_location_rejects_an_unknown_location():
    world = World()
    with pytest.raises(AssertionError):
        harness_portability_steps._project_with_persistent_location(
            world,
            {
                "_step_text": (
                    "a temporary project whose config places its persistent "
                    "root in the nowhere"
                ),
                "location": "nowhere",
            },
        )
