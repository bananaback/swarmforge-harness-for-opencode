"""Property tests for the harness status row parser.

``parse_status_rows`` is the only place the acceptance suite turns the
``harness status`` text back into structured rows, so its contract is that any
line the CLI renders as ``LABEL [marker] path`` round-trips, and that lines
without a marker are ignored.
"""

import sys
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

ACCEPTANCE = Path(__file__).resolve().parents[1] / "acceptance"
sys.path.insert(0, str(ACCEPTANCE))

from steps.harness_cli_steps import parse_status_rows  # noqa: E402

LABELS = st.from_regex(r"[A-Z][A-Z0-9_]{0,15}", fullmatch=True)
MARKERS = st.sampled_from(["ok", "-"])
# A path the CLI prints on one stripped line: printable ASCII, no line breaks,
# no leading/trailing whitespace, but spaces inside are fine.
_EDGE = r"[\x21-\x7e]"
_INNER = r"[\x20-\x7e]"
PATHS = st.from_regex(rf"{_EDGE}(?:{_INNER}*{_EDGE})?", fullmatch=True)
SETTINGS = settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@SETTINGS
@given(label=LABELS, marker=MARKERS, path=PATHS)
def test_status_row_round_trips(label, marker, path):
    line = f"{label:<10} [{marker}] {path}"
    assert parse_status_rows(line) == {label: (marker, path)}


@SETTINGS
@given(label=LABELS, marker=MARKERS, path=PATHS)
def test_status_rows_ignore_unmarked_lines(label, marker, path):
    stdout = f"{label:<10} [{marker}] {path}\nnot a status row\n\n"
    assert parse_status_rows(stdout) == {label: (marker, path)}
