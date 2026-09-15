"""Property tests for ``harness._in_process_count``.

The counter decides whether ``clean state`` refuses, so its invariant is exact
conservation: it counts every live in-process mail item plus every live team
task, and nothing else.
"""

import datetime
import importlib.util
import shutil
from importlib.machinery import SourceFileLoader
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

TOOLS = Path(__file__).resolve().parents[2].parent / "tools"


def load_harness():
    loader = SourceFileLoader("harness_tool", str(TOOLS / "harness"))
    spec = importlib.util.spec_from_loader("harness_tool", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


ROLE = st.from_regex(r"[a-z][a-z0-9-]{0,7}", fullmatch=True)
SEGMENT = st.from_regex(r"[A-Za-z0-9][A-Za-z0-9._-]{0,7}", fullmatch=True)
TASK = st.lists(SEGMENT, min_size=1, max_size=3).map("/".join)
DATE = st.dates(
    min_value=datetime.date(2000, 1, 1), max_value=datetime.date(2035, 12, 31)
)
SETTINGS = settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@SETTINGS
@given(
    roles=st.lists(ROLE, max_size=4, unique=True),
    tasks=st.lists(st.tuples(DATE, TASK), max_size=4, unique_by=lambda item: item),
)
def test_in_process_count_is_the_sum_of_mail_and_task_items(tmp_path, roles, tasks):
    harness = load_harness()
    state = tmp_path / "state"
    shutil.rmtree(state, ignore_errors=True)

    for index, role in enumerate(roles):
        inbox = state / "mail" / "inbox" / role / "in_process"
        inbox.mkdir(parents=True, exist_ok=True)
        (inbox / f"{index:02d}.json").write_text("{}")
    for date, task in tasks:
        folder = state / "tasks" / date.isoformat() / task
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "task.json").write_text("{}")

    # Decoys that share the shapes but must not be counted.
    queued = state / "mail" / "inbox" / "ghost" / "queued"
    queued.mkdir(parents=True, exist_ok=True)
    (queued / "01.json").write_text("{}")
    other = state / "tasks" / "2020-01-01" / "ghost"
    other.mkdir(parents=True, exist_ok=True)
    (other / "output.json").write_text("{}")

    assert harness._in_process_count(state) == len(roles) + len(tasks)
