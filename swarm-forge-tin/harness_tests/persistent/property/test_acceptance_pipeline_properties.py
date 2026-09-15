"""Property tests for the acceptance-pipeline dry-report handlers.

``_dry_report_kinds`` is the handler that pins a dry report's finding-kind set to
the feature's expected set. Its contract is exact equality after trimming the
comma-separated cell: the handler accepts iff the report's kinds are exactly the
named kinds, so an extra finding kind is never allowed through.
"""

import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

ACCEPTANCE = Path(__file__).resolve().parents[1] / "acceptance"
sys.path.insert(0, str(ACCEPTANCE))

from runtime import World  # noqa: E402
from steps import acceptance_pipeline_steps  # noqa: E402

KINDS = st.from_regex(r"[a-z][a-z0-9-]{0,20}", fullmatch=True)
SETTINGS = settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


def _step_text(expected_kinds: set[str]) -> str:
    return 'the dry report contains only the "{}" kinds'.format(
        ", ".join(sorted(expected_kinds))
    )


@SETTINGS
@given(
    report_kinds=st.sets(KINDS, max_size=5),
    expected_kinds=st.sets(KINDS, max_size=5),
)
def test_dry_report_kinds_accepts_exactly_the_named_set(
    report_kinds, expected_kinds
):
    world = World()
    world.state["dry_report"] = {
        "findings": [{"kind": kind} for kind in report_kinds]
    }
    examples = {"_step_text": _step_text(expected_kinds)}
    if report_kinds == expected_kinds:
        acceptance_pipeline_steps._dry_report_kinds(world, examples)
    else:
        with pytest.raises(AssertionError):
            acceptance_pipeline_steps._dry_report_kinds(world, examples)
