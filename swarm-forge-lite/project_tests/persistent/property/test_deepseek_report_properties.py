"""Property tests for DeepSeek pricing and day bucketing."""

import datetime
from dataclasses import replace

import pytest
from deepseek_report import (
    ALIASES,
    GO_PROVIDER,
    PRICES,
    Request,
    build_report,
    is_peak,
    parse_requests,
    request_cost,
)
from hypothesis import given
from hypothesis import strategies as st

_tokens = st.integers(min_value=0, max_value=10**12)
_costs = st.floats(
    min_value=0, max_value=10**9, allow_nan=False, allow_infinity=False
)
_dates = st.dates(
    min_value=datetime.date(2020, 1, 1), max_value=datetime.date(2030, 12, 31)
)
_hours = st.integers(min_value=0, max_value=23)
_minutes = st.integers(min_value=0, max_value=59)
_providers = st.sampled_from([GO_PROVIDER, "deepseek"])
_models = st.sampled_from(
    sorted(PRICES) + ["deepseek-unknown", "other-unknown"]
)
_priced_models = st.sampled_from(sorted(PRICES))

# A Monday, so 02:00 is peak and 00:00 is off-peak.
_PEAK_MOMENT = datetime.datetime(
    2026, 9, 7, 2, 0, tzinfo=datetime.timezone.utc
)
_OFF_MOMENT = datetime.datetime(
    2026, 9, 7, 0, 0, tzinfo=datetime.timezone.utc
)


def _moment(date, hour, minute):
    return datetime.datetime(
        date.year, date.month, date.day, hour, minute,
        tzinfo=datetime.timezone.utc,
    )


def _request(
    timestamp,
    provider=GO_PROVIDER,
    model="deepseek-v4.1-flash",
    input=0,
    output=0,
    reasoning=0,
    cache_read=0,
    cache_write=0,
    stored_cost=0.0,
):
    return Request(
        timestamp=timestamp,
        provider=provider,
        model=model,
        input=input,
        output=output,
        reasoning=reasoning,
        cache_read=cache_read,
        cache_write=cache_write,
        stored_cost=stored_cost,
    )


def _format(request):
    return ",".join(
        (
            request.timestamp.strftime("%Y-%m-%dT%H:%M"),
            request.provider,
            request.model,
            str(request.input),
            str(request.output),
            str(request.reasoning),
            str(request.cache_read),
            str(request.cache_write),
            str(request.stored_cost),
        )
    )


@st.composite
def requests(draw):
    return Request(
        timestamp=_moment(draw(_dates), draw(_hours), draw(_minutes)),
        provider=draw(_providers),
        model=draw(_models),
        input=draw(_tokens),
        output=draw(_tokens),
        reasoning=draw(_tokens),
        cache_read=draw(_tokens),
        cache_write=draw(_tokens),
        stored_cost=draw(_costs),
    )


# --- Pricing ---------------------------------------------------------------


@given(requests())
def test_request_cost_is_non_negative_and_finite(request):
    cost = request_cost(request)
    assert cost >= 0
    assert cost != float("inf")


@given(requests())
def test_non_go_requests_are_never_priced(request):
    if request.provider != GO_PROVIDER:
        assert request_cost(request) == 0


@given(requests())
def test_unknown_models_are_never_priced(request):
    if request.model not in PRICES and request.model not in ALIASES:
        assert request_cost(request) == 0


@given(requests())
def test_cost_matches_the_published_rate_table(request):
    price = PRICES.get(ALIASES.get(request.model, request.model))
    if request.provider != GO_PROVIDER or price is None:
        assert request_cost(request) == 0
        return
    input_rate, output_rate, cache_rate = (
        price["peak"] if is_peak(request.timestamp) else price["off"]
    )
    expected = (
        request.input * input_rate
        + (request.output + request.reasoning) * output_rate
        + request.cache_read * cache_rate
    ) / 1e6
    assert request_cost(request) == pytest.approx(expected, rel=1e-12, abs=1e-15)


@given(requests(), st.integers(min_value=1, max_value=1000))
def test_cost_is_linear_in_the_token_counts(request, factor):
    scaled = replace(
        request,
        input=request.input * factor,
        output=request.output * factor,
        reasoning=request.reasoning * factor,
        cache_read=request.cache_read * factor,
    )
    assert request_cost(scaled) == pytest.approx(
        request_cost(request) * factor, rel=1e-9, abs=1e-18
    )


@given(requests())
def test_cache_write_is_counted_but_never_priced(request):
    only_write = replace(
        request, input=0, output=0, reasoning=0, cache_read=0
    )
    assert request_cost(only_write) == 0


@given(
    _priced_models,
    _tokens,
    _tokens,
    _tokens,
    _tokens,
    _tokens,
)
def test_peak_rate_is_never_cheaper_than_off_peak(
    model, input, output, reasoning, cache_read, cache_write
):
    tokens = {
        "input": input,
        "output": output,
        "reasoning": reasoning,
        "cache_read": cache_read,
        "cache_write": cache_write,
    }
    peak = _request(_PEAK_MOMENT, model=model, **tokens)
    off = _request(_OFF_MOMENT, model=model, **tokens)
    assert request_cost(peak) >= request_cost(off)


@given(
    st.sampled_from(sorted(ALIASES)),
    _tokens,
    _tokens,
    _tokens,
    _tokens,
    _tokens,
)
def test_alias_is_priced_as_its_current_model(
    model, input, output, reasoning, cache_read, cache_write
):
    tokens = {
        "input": input,
        "output": output,
        "reasoning": reasoning,
        "cache_read": cache_read,
        "cache_write": cache_write,
    }
    alias = _request(_OFF_MOMENT, model=model, **tokens)
    current = _request(_OFF_MOMENT, model=ALIASES[model], **tokens)
    assert request_cost(alias) == pytest.approx(request_cost(current))


# --- Parsing ---------------------------------------------------------------


@given(requests())
def test_parse_round_trip_preserves_every_field(request):
    assert parse_requests(_format(request)) == [request]


@given(st.lists(requests(), max_size=5))
def test_parse_splits_semicolon_separated_requests(request_list):
    assert parse_requests(";".join(map(_format, request_list))) == request_list


# --- Bucketing -------------------------------------------------------------


@given(st.lists(requests(), max_size=20))
def test_report_conserves_every_total(request_list):
    report = build_report(request_list)
    days = list(report.days)
    assert sum(day.requests for day in days) == len(request_list)
    assert sum(day.input for day in days) == sum(r.input for r in request_list)
    assert sum(day.output for day in days) == sum(
        r.output + r.reasoning for r in request_list
    )
    assert sum(day.cache_read for day in days) == sum(
        r.cache_read for r in request_list
    )
    assert sum(day.cache_write for day in days) == sum(
        r.cache_write for r in request_list
    )


@given(st.lists(requests(), min_size=1, max_size=20))
def test_report_covers_every_day_from_first_to_last(request_list):
    report = build_report(request_list)
    dates = [request.timestamp.date() for request in request_list]
    expected = []
    cursor = min(dates)
    while cursor <= max(dates):
        expected.append(cursor)
        cursor += datetime.timedelta(days=1)
    assert [day.date for day in report.days] == expected
    assert [day.label for day in report.days] == [
        date.strftime("%m/%d") for date in expected
    ]


@given(
    st.lists(requests(), max_size=10),
    _dates,
    st.integers(min_value=0, max_value=10),
)
def test_explicit_range_reports_every_day_including_empty(
    request_list, start, span
):
    end = start + datetime.timedelta(days=span)
    report = build_report(request_list, start=start, end=end)
    expected = [start + datetime.timedelta(days=i) for i in range(span + 1)]
    assert [day.date for day in report.days] == expected
    in_range = [
        request
        for request in request_list
        if start <= request.timestamp.date() <= end
    ]
    assert sum(day.requests for day in report.days) == len(in_range)
    for day in report.days:
        if day.requests == 0:
            assert day.input == 0
            assert day.output == 0
            assert day.go_reported == 0
            assert day.go_cost == 0


@given(st.lists(requests(), max_size=20))
def test_go_reported_is_the_stored_cost_of_priced_go_requests(request_list):
    report = build_report(request_list)
    expected = sum(
        request.stored_cost
        for request in request_list
        if request.provider == GO_PROVIDER
        and ALIASES.get(request.model, request.model) in PRICES
    )
    actual = sum(day.go_reported for day in report.days)
    assert actual == pytest.approx(expected, rel=1e-9, abs=1e-12)


@given(st.lists(requests(), max_size=20))
def test_report_is_order_independent(request_list):
    forward = build_report(request_list)
    backward = build_report(list(reversed(request_list)))
    assert [day.date for day in forward.days] == [
        day.date for day in backward.days
    ]
    for left, right in zip(forward.days, backward.days):
        assert left.requests == right.requests
        assert left.input == right.input
        assert left.output == right.output
        assert left.cache_read == right.cache_read
        assert left.cache_write == right.cache_write
        assert left.go_reported == pytest.approx(right.go_reported)
        assert left.go_cost == pytest.approx(right.go_cost)
