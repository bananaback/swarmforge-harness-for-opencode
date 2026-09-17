"""Unit tests for the token-usage domain calculations."""

import pytest
from usage import Session, parse_sessions, session_usage, summarize


def test_total_input_adds_input_and_cache_read():
    usage = session_usage(Session(input=1000, cache_read=400))
    assert usage.total_input == 1400


def test_total_input_is_just_input_without_cache_read():
    usage = session_usage(Session(input=3000))
    assert usage.total_input == 3000


def test_total_output_adds_output_and_reasoning():
    usage = session_usage(Session(output=200, reasoning=50))
    assert usage.total_output == 250


def test_cache_hit_is_cache_read_over_total_input():
    usage = session_usage(Session(input=750, cache_read=250))
    assert usage.cache_hit == pytest.approx(0.25)


def test_cache_hit_is_zero_when_total_input_is_zero():
    usage = session_usage(Session(output=200, reasoning=50))
    assert usage.cache_hit == 0


def test_output_ratio_is_total_output_over_total_input():
    usage = session_usage(Session(input=500, output=400, reasoning=100, cache_read=500))
    assert usage.output_ratio == pytest.approx(0.5)


def test_output_ratio_is_zero_when_total_input_is_zero():
    usage = session_usage(Session(output=200, reasoning=50))
    assert usage.output_ratio == 0


def test_cost_is_reported_unchanged():
    usage = session_usage(Session(cost=0.25))
    assert usage.cost == 0.25


def test_parse_sessions_reads_each_field_in_order():
    assert parse_sessions("1000,200,50,400,10,0.25,3") == [
        Session(
            input=1000,
            output=200,
            reasoning=50,
            cache_read=400,
            cache_write=10,
            cost=0.25,
            requests=3,
        )
    ]


def test_parse_sessions_splits_on_semicolons():
    sessions = parse_sessions("1000,200,50,400,10,0.25,3;2000,100,0,0,0,0.5,5")
    assert [session.input for session in sessions] == [1000, 2000]


def test_parse_sessions_empty_is_no_sessions():
    assert parse_sessions("") == []


def test_summary_counts_sessions():
    assert summarize([Session(), Session()]).sessions == 2


def test_summary_sums_requests():
    summary = summarize(parse_sessions("1000,200,50,400,10,0.25,3;2000,100,0,0,0,0.5,5"))
    assert summary.requests == 8


def test_summary_total_input_sums_inputs_and_cache_reads():
    summary = summarize(parse_sessions("1000,200,50,400,10,0.25,3;2000,100,0,0,0,0.5,5"))
    assert summary.total_input == 3400


def test_summary_total_output_sums_outputs_and_reasonings():
    summary = summarize(parse_sessions("1000,200,50,400,10,0.25,3;2000,100,0,0,0,0.5,5"))
    assert summary.total_output == 350


def test_summary_cache_hit_is_cache_reads_over_total_input():
    summary = summarize(parse_sessions("1000,200,50,400,10,0.25,3"))
    assert summary.cache_hit == pytest.approx(0.285714, abs=1e-6)


def test_summary_output_ratio_is_total_output_over_total_input():
    summary = summarize(parse_sessions("1000,200,50,400,10,0.25,3"))
    assert summary.output_ratio == pytest.approx(0.178571, abs=1e-6)


def test_summary_cost_sums_session_costs():
    summary = summarize(parse_sessions("1000,200,50,400,10,0.25,3;2000,100,0,0,0,0.5,5"))
    assert summary.cost == pytest.approx(0.75)


def test_summary_of_no_sessions_is_zero():
    summary = summarize(parse_sessions(""))
    assert summary.sessions == 0
    assert summary.requests == 0
    assert summary.total_input == 0
    assert summary.total_output == 0
    assert summary.cache_hit == 0
    assert summary.output_ratio == 0
    assert summary.cost == 0


def test_summary_ratios_are_zero_when_total_input_is_zero():
    summary = summarize([Session(output=200, reasoning=50)])
    assert summary.cache_hit == 0
    assert summary.output_ratio == 0
