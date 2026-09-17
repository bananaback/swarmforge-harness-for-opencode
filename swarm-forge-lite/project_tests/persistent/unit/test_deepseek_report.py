"""Unit tests for the DeepSeek per-request report."""

import datetime

import pytest
from deepseek_report import (
    build_report,
    is_go_priced,
    is_peak,
    parse_requests,
    request_cost,
)


def _request(
    timestamp,
    provider="opencode-go",
    model="deepseek-v4.1-flash",
    input=0,
    output=0,
    reasoning=0,
    cache_read=0,
    cache_write=0,
    stored_cost=0.0,
):
    return (
        f"{timestamp},{provider},{model},{input},{output},{reasoning},"
        f"{cache_read},{cache_write},{stored_cost}"
    )


def _report(requests, start=None, end=None):
    return build_report(parse_requests(requests), start=start, end=end)


def _day(report, label):
    return report.day(label)


def test_parse_reads_every_field_in_order():
    request = parse_requests(
        "2026-09-07T00:10,opencode-go,deepseek-v4.1-flash,1000000,500000,200000,"
        "100,50,0.45"
    )[0]
    assert request.timestamp == datetime.datetime(
        2026, 9, 7, 0, 10, tzinfo=datetime.timezone.utc
    )
    assert request.provider == "opencode-go"
    assert request.model == "deepseek-v4.1-flash"
    assert request.input == 1000000
    assert request.output == 500000
    assert request.reasoning == 200000
    assert request.cache_read == 100
    assert request.cache_write == 50
    assert request.stored_cost == 0.45


def test_parse_splits_requests_on_semicolons():
    requests = parse_requests(
        f"{_request('2026-09-07T00:10')};{_request('2026-09-07T04:30')}"
    )
    assert len(requests) == 2


def test_parse_empty_is_no_requests():
    assert parse_requests("") == []


def test_each_request_counts_once_on_the_day_it_was_made():
    report = _report(
        f"{_request('2026-09-07T00:10')};{_request('2026-09-07T04:30')}"
    )
    assert _day(report, "09/07").requests == 2


def test_requests_are_bucketed_by_their_own_day():
    report = _report(
        f"{_request('2026-09-07T00:10')};{_request('2026-09-08T00:10')}"
    )
    assert _day(report, "09/07").requests == 1
    assert _day(report, "09/08").requests == 1


def test_input_tokens_are_summed_per_day():
    report = _report(
        f"{_request('2026-09-07T00:10', input=1000000)};"
        f"{_request('2026-09-07T04:30', input=2000000)}"
    )
    assert _day(report, "09/07").input == 3000000


def test_output_tokens_add_reasoning():
    report = _report(
        _request("2026-09-07T00:10", output=300000, reasoning=200000)
    )
    assert _day(report, "09/07").output == 500000


def test_cache_read_tokens_are_summed_per_day():
    report = _report(
        f"{_request('2026-09-07T04:30', cache_read=1000000)};"
        f"{_request('2026-09-07T05:00', cache_read=2000000)}"
    )
    assert _day(report, "09/07").cache_read == 3000000


def test_cache_write_tokens_are_summed_per_day():
    report = _report(
        f"{_request('2026-09-07T04:30', cache_write=100)};"
        f"{_request('2026-09-07T05:00', cache_write=200)}"
    )
    assert _day(report, "09/07").cache_write == 300


def test_go_reported_cost_is_the_stored_cost_of_go_requests():
    report = _report(
        f"{_request('2026-09-07T02:00', input=1000000, stored_cost=0.15)};"
        f"{_request('2026-09-07T04:30', cache_read=1000000, stored_cost=0.003)}"
    )
    assert round(_day(report, "09/07").go_reported, 6) == 0.153


def test_non_go_provider_is_counted_but_carries_no_go_cost():
    report = _report(
        f"{_request('2026-09-07T00:10', input=1000000, stored_cost=0.15)};"
        f"{_request('2026-09-07T00:20', provider='deepseek', input=1000000, stored_cost=0.10)}"
    )
    day = _day(report, "09/07")
    assert day.requests == 2
    assert day.go_reported == pytest.approx(0.15)
    assert day.go_cost == pytest.approx(0.15)


def test_peak_aware_cost_uses_the_peak_rate():
    report = _report(
        _request("2026-09-08T02:00", input=1000000, output=300000, reasoning=200000,
                 stored_cost=0.45)
    )
    assert round(_day(report, "09/08").go_cost, 6) == 0.9


def test_peak_aware_cost_uses_the_off_peak_rate():
    report = _report(_request("2026-09-07T04:30", input=1000000, stored_cost=0.15))
    assert round(_day(report, "09/07").go_cost, 6) == 0.15


@pytest.mark.parametrize(
    "timestamp,peak",
    [
        ("2026-09-07T00:00", False),
        ("2026-09-07T00:59", False),
        ("2026-09-07T01:00", True),
        ("2026-09-07T03:59", True),
        ("2026-09-07T04:00", False),
        ("2026-09-07T05:59", False),
        ("2026-09-07T06:00", True),
        ("2026-09-07T09:59", True),
        ("2026-09-07T10:00", False),
        ("2026-09-07T23:59", False),
        ("2026-09-05T02:00", False),
        ("2026-09-06T02:00", False),
    ],
)
def test_peak_is_weekday_01_00_04_00_and_06_00_10_00_utc(timestamp, peak):
    moment = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M").replace(
        tzinfo=datetime.timezone.utc
    )
    assert is_peak(moment) is peak


@pytest.mark.parametrize(
    "timestamp,go_cost",
    [
        ("2026-09-07T00:00", 0.15),
        ("2026-09-07T01:00", 0.3),
        ("2026-09-07T04:00", 0.15),
        ("2026-09-07T06:00", 0.3),
        ("2026-09-07T10:00", 0.15),
    ],
)
def test_peak_aware_cost_picks_the_rate_of_the_hour(timestamp, go_cost):
    report = _report(_request(timestamp, input=1000000))
    assert round(_day(report, "09/07").go_cost, 6) == go_cost


def test_each_model_is_priced_at_its_own_rates():
    report = _report(
        _request("2026-09-07T00:10", model="deepseek-v4-pro", input=1000000,
                 output=500000)
    )
    assert round(_day(report, "09/07").go_cost, 6) == 1.65


def test_retired_model_name_is_priced_as_its_current_model():
    report = _report(
        _request("2026-09-07T00:10", model="deepseek-flash", input=1000000,
                 output=500000)
    )
    assert round(_day(report, "09/07").go_cost, 6) == 0.45


def test_cache_write_tokens_are_counted_but_not_priced():
    report = _report(
        _request("2026-09-07T00:10", cache_write=1000000, stored_cost=0.0)
    )
    day = _day(report, "09/07")
    assert day.cache_write == 1000000
    assert day.go_cost == 0


def test_unknown_model_has_no_go_cost():
    report = _report(_request("2026-09-07T00:10", model="deepseek-unknown"))
    assert _day(report, "09/07").go_cost == 0


def test_explicit_range_reports_days_with_no_requests():
    report = _report(
        _request("2026-09-08T00:10", input=1000000, stored_cost=0.15),
        start=datetime.date(2026, 9, 7),
        end=datetime.date(2026, 9, 9),
    )
    assert [day.label for day in report.days] == ["09/07", "09/08", "09/09"]
    assert _day(report, "09/07").requests == 0
    assert _day(report, "09/08").requests == 1
    assert _day(report, "09/09").requests == 0


def test_default_range_spans_first_through_last_request_day():
    report = _report(
        f"{_request('2026-09-07T00:10')};{_request('2026-09-09T00:10')}"
    )
    assert [day.label for day in report.days] == ["09/07", "09/08", "09/09"]


def test_report_day_unknown_label_raises():
    report = _report(_request("2026-09-07T00:10"))
    with pytest.raises(KeyError):
        report.day("09/08")


def test_request_cost_is_zero_for_non_go_provider():
    request = parse_requests(
        _request("2026-09-07T02:00", provider="deepseek", input=1000000)
    )[0]
    assert request_cost(request) == 0.0


def test_request_cost_is_zero_for_unknown_model():
    request = parse_requests(
        _request("2026-09-07T02:00", model="deepseek-unknown", input=1000000)
    )[0]
    assert request_cost(request) == 0.0


@pytest.mark.parametrize(
    "provider,model,priced",
    [
        ("opencode-go", "deepseek-v4.1-flash", True),
        ("opencode-go", "deepseek-v4-pro", True),
        ("opencode-go", "deepseek-flash", True),
        ("deepseek", "deepseek-v4.1-flash", False),
        ("opencode-go", "deepseek-unknown", False),
        ("opencode-go", "other-unknown", False),
    ],
)
def test_is_go_priced_requires_go_provider_and_a_priced_model(provider, model, priced):
    request = parse_requests(
        _request("2026-09-07T02:00", provider=provider, model=model)
    )[0]
    assert is_go_priced(request) is priced
