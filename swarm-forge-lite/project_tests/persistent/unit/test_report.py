"""Unit tests for the database-row token-usage adapters."""

import pytest
from report import stats, summarize


def _row(**overrides):
    row = {'ti': 1000, 'to': 200, 'tr': 50, 'tcr': 400, 'tcw': 10, 'cost': 0.25}
    row.update(overrides)
    return row


def test_stats_maps_input_output_and_reasoning():
    result = stats(_row())
    assert result['input'] == 1000
    assert result['output'] == 250
    assert result['reasoning'] == 50


def test_stats_maps_cache_read_and_write_through():
    result = stats(_row())
    assert result['cache_read'] == 400


def test_stats_total_is_input_plus_total_output():
    assert stats(_row())['total'] == 1250


def test_stats_ratios_use_total_input():
    result = stats(_row())
    assert result['cache_hit'] == pytest.approx(400 / 1400)
    assert result['output_ratio'] == pytest.approx(250 / 1400)


def test_stats_ratios_are_zero_without_total_input():
    result = stats(_row(ti=0, tcr=0))
    assert result['cache_hit'] == 0
    assert result['output_ratio'] == 0


def test_stats_cost_is_reported_unchanged():
    assert stats(_row(cost=0.5))['cost'] == 0.5


def test_summarize_counts_sessions_and_requests():
    result = summarize([_row(requests=3), _row(requests=5)])
    assert result['sessions'] == 2
    assert result['requests'] == 8


def test_summarize_defaults_missing_requests_to_zero():
    assert summarize([_row()])['requests'] == 0


def test_summarize_sums_every_field():
    result = summarize([_row(requests=3), _row(ti=2000, to=100, tr=0, tcr=0, tcw=0, cost=0.5, requests=5)])
    assert result['input'] == 3000
    assert result['output'] == 350
    assert result['reasoning'] == 50
    assert result['cache_read'] == 400
    assert result['cache_write'] == 10
    assert result['total_input'] == 3400
    assert result['cost'] == pytest.approx(0.75)


def test_summarize_ratios_use_aggregate_totals():
    result = summarize([_row(requests=3), _row(ti=2000, to=100, tr=0, tcr=0, tcw=0, cost=0.5, requests=5)])
    assert result['cache_hit'] == pytest.approx(400 / 3400)
    assert result['output_ratio'] == pytest.approx(350 / 3400)


def test_summarize_of_no_rows_is_zero():
    result = summarize([])
    assert result['sessions'] == 0
    assert result['requests'] == 0
    assert result['total_input'] == 0
    assert result['output'] == 0
    assert result['cache_hit'] == 0
    assert result['output_ratio'] == 0
    assert result['cost'] == 0
