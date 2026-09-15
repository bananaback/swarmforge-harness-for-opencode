"""Property tests for the task-breaker bridge's pure plan and staging helpers."""

import taskbreak
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

VALID_SEGMENT = st.from_regex(r"[A-Za-z0-9][A-Za-z0-9._-]{0,7}", fullmatch=True)
VALID_TASK = st.lists(VALID_SEGMENT, min_size=1, max_size=3).map("/".join)
SETTINGS = settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@SETTINGS
@given(value=st.text(max_size=30))
def test_slug_is_safe_and_idempotent(value):
    result = taskbreak.slug(value)
    assert result
    assert "/" not in result and "\\" not in result
    assert not result.startswith(("-", "."))
    assert not result.endswith(("-", "."))
    assert taskbreak.slug(result) == result


@SETTINGS
@given(text=st.text(max_size=40), oracle=st.text(max_size=20))
def test_with_oracle_is_idempotent(text, oracle):
    once = taskbreak.with_oracle(text, oracle)
    assert taskbreak.with_oracle(once, oracle) == once


@SETTINGS
@given(text=st.text(max_size=40), oracle=st.text(max_size=20))
def test_with_oracle_preserves_text_and_appends_one_section(text, oracle):
    once = taskbreak.with_oracle(text, oracle)
    already = any(line.strip().upper() == taskbreak.ORACLE_HEADER for line in text.splitlines())
    if not oracle or already:
        assert once == text
    else:
        assert once == f"{text.rstrip()}\n\n{taskbreak.ORACLE_HEADER}\n{oracle}\n"


@SETTINGS
@given(version=st.integers(min_value=-5, max_value=5).filter(lambda value: value != 1))
def test_plan_version_other_than_one_is_refused(version):
    problems = taskbreak.plan_problems(
        {
            "version": version,
            "chunks": [{"task": "cart", "role": "coder", "brief_text": "x"}],
        }
    )
    assert problems == [f"plan version must be {taskbreak.PLAN_VERSION}"]


@SETTINGS
@given(task=VALID_TASK)
def test_valid_chunk_task_produces_no_problems(task):
    problems = taskbreak.plan_problems(
        {
            "version": 1,
            "chunks": [{"task": task, "role": "coder", "brief_text": "x"}],
        }
    )
    assert problems == []
