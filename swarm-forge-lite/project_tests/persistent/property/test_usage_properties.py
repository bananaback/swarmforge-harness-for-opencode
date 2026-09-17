"""Property tests for the token-usage domain calculations."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from usage import Session, parse_sessions, session_usage, summarize

_tokens = st.integers(min_value=0, max_value=10**12)
_costs = st.floats(
    min_value=0, max_value=10**9, allow_nan=False, allow_infinity=False
)


@st.composite
def sessions(draw):
    return Session(
        input=draw(_tokens),
        output=draw(_tokens),
        reasoning=draw(_tokens),
        cache_read=draw(_tokens),
        cache_write=draw(_tokens),
        cost=draw(_costs),
        requests=draw(_tokens),
    )


@given(sessions())
def test_totals_add_cache_read_and_reasoning(session):
    usage = session_usage(session)
    assert usage.total_input == session.input + session.cache_read
    assert usage.total_output == session.output + session.reasoning


@given(sessions())
def test_session_cost_is_preserved(session):
    assert session_usage(session).cost == session.cost


@given(sessions())
def test_cache_hit_is_a_fraction_of_total_input(session):
    usage = session_usage(session)
    if usage.total_input == 0:
        assert usage.cache_hit == 0
    else:
        assert usage.cache_hit == session.cache_read / usage.total_input
        assert 0 <= usage.cache_hit <= 1


@given(sessions())
def test_output_ratio_is_total_output_over_total_input(session):
    usage = session_usage(session)
    if usage.total_input == 0:
        assert usage.output_ratio == 0
    else:
        assert usage.output_ratio == usage.total_output / usage.total_input
        assert usage.output_ratio >= 0


@given(st.lists(sessions(), max_size=20))
def test_summary_conserves_every_total(session_list):
    summary = summarize(session_list)
    assert summary.sessions == len(session_list)
    assert summary.requests == sum(s.requests for s in session_list)
    assert summary.total_input == sum(
        session_usage(s).total_input for s in session_list
    )
    assert summary.total_output == sum(
        session_usage(s).total_output for s in session_list
    )
    assert summary.cost == sum(s.cost for s in session_list)


@given(st.lists(sessions(), max_size=20))
def test_summary_ratios_match_its_totals(session_list):
    summary = summarize(session_list)
    if summary.total_input == 0:
        assert summary.cache_hit == 0
        assert summary.output_ratio == 0
    else:
        assert summary.cache_hit == summary.cache_read / summary.total_input
        assert summary.output_ratio == summary.total_output / summary.total_input


@given(st.lists(sessions(), max_size=10))
def test_summary_is_order_independent(session_list):
    forward = summarize(session_list)
    backward = summarize(list(reversed(session_list)))
    assert forward.sessions == backward.sessions
    assert forward.total_input == backward.total_input
    assert forward.total_output == backward.total_output
    assert forward.cost == pytest.approx(backward.cost)


@given(sessions())
def test_parse_round_trip_preserves_every_field(session):
    text = ",".join(
        str(value)
        for value in (
            session.input,
            session.output,
            session.reasoning,
            session.cache_read,
            session.cache_write,
            session.cost,
            session.requests,
        )
    )
    assert parse_sessions(text) == [session]


@given(st.lists(sessions(), min_size=1, max_size=5))
def test_parse_splits_semicolon_separated_sessions(session_list):
    text = ";".join(
        ",".join(
            str(value)
            for value in (
                s.input,
                s.output,
                s.reasoning,
                s.cache_read,
                s.cache_write,
                s.cost,
                s.requests,
            )
        )
        for s in session_list
    )
    assert parse_sessions(text) == session_list


@given(st.text(alphabet=" \t\n\r"))
def test_parse_of_whitespace_is_no_sessions(text):
    assert parse_sessions(text) == []
