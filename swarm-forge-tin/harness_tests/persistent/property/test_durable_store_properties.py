"""Property tests for the durable JSON store primitives.

``durable_store`` is the shared storage boundary for the mail and team tools, so
its contracts are broad: any JSON document round-trips through an atomic write,
an atomic write never leaves a temp file behind, ``list_json`` returns exactly
the sorted non-dot ``.json`` files, and ``next_seq`` is monotonic from any
starting value.
"""

import re
import uuid
from datetime import datetime

import durable_store
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

SETTINGS = settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)

JSON_SCALARS = (
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text()
)
JSON_VALUES = st.recursive(
    JSON_SCALARS,
    lambda children: (
        st.lists(children, max_size=4)
        | st.dictionaries(st.text(), children, max_size=4)
    ),
    max_leaves=8,
)

_SAFE_NAME = st.from_regex(r"[A-Za-z0-9_-]{1,8}", fullmatch=True)
_SUFFIXES = st.sampled_from([".json", ".txt", ".md"])
_FILENAMES = st.tuples(_SAFE_NAME, _SUFFIXES).map(lambda parts: "".join(parts))
_STARTS = st.integers(min_value=-1_000_000, max_value=1_000_000)


@SETTINGS
@given(document=JSON_VALUES)
def test_atomic_write_round_trips_any_json_document(tmp_path, document):
    path = tmp_path / "doc.json"
    durable_store.write_json_atomic(path, document)
    assert durable_store.read_json(path) == document


@SETTINGS
@given(document=JSON_VALUES)
def test_atomic_write_leaves_only_the_document(tmp_path, document):
    path = tmp_path / "nested" / "doc.json"
    durable_store.write_json_atomic(path, document)
    assert sorted(child.name for child in path.parent.iterdir()) == ["doc.json"]


@SETTINGS
@given(names=st.lists(_FILENAMES, max_size=8))
def test_list_json_returns_sorted_non_dot_json_files(tmp_path, names):
    directory = tmp_path / uuid.uuid4().hex
    directory.mkdir()
    for name in sorted(set(names)):
        (directory / name).write_text("{}")
    expected = sorted(
        name for name in set(names) if name.endswith(".json") and not name.startswith(".")
    )
    assert [path.name for path in durable_store.list_json(directory)] == expected


def test_list_json_of_a_missing_directory_is_empty(tmp_path):
    assert durable_store.list_json(tmp_path / "absent") == []


@SETTINGS
@given(start=_STARTS, calls=st.integers(min_value=0, max_value=8))
def test_next_seq_is_monotonic_from_any_start(tmp_path, start, calls):
    path = tmp_path / f"{uuid.uuid4().hex}.txt"
    path.write_text(f"{start}\n")
    allocated = [durable_store.next_seq(path) for _ in range(calls)]
    assert allocated == list(range(start + 1, start + 1 + calls))
    assert allocated == sorted(allocated)


@SETTINGS
@given(calls=st.integers(min_value=1, max_value=5))
def test_next_seq_starts_at_one_for_a_missing_file(tmp_path, calls):
    path = tmp_path / f"{uuid.uuid4().hex}.txt"
    allocated = [durable_store.next_seq(path) for _ in range(calls)]
    assert allocated == list(range(1, calls + 1))


@SETTINGS
@given(garbage=st.text(alphabet="abcxyz .", min_size=1, max_size=10))
def test_next_seq_treats_a_non_numeric_counter_as_zero(tmp_path, garbage):
    path = tmp_path / f"{uuid.uuid4().hex}.txt"
    path.write_text(garbage)
    assert durable_store.next_seq(path) == 1


def test_iso_now_is_a_documented_utc_stamp():
    stamp = durable_store.iso_now()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", stamp)
    parsed = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    assert parsed is not None
