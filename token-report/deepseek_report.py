"""DeepSeek per-request cost report.

A requests value encodes one or more requests separated by ``;``. Each request
is ``timestamp,provider,model,input,output,reasoning,cache_read,cache_write,
stored_cost`` with a UTC ``YYYY-MM-DDTHH:MM`` timestamp. One request is one
billable provider call, bucketed by the day it was made.

Two costs are reported for the same requests: ``go_reported`` is the stored
cost the ``opencode-go`` provider recorded, and ``go_cost`` re-prices the same
tokens at the OpenCode Go peak/off-peak table. Cache write is not priced and
reasoning is billed at the output rate.
"""

import datetime
from dataclasses import dataclass

# USD per 1M tokens: (input, output, cache read). Cache write is unpriced.
_OFF_PEAK = (0.15, 0.60, 0.003)
_FLASH_PEAK = (0.30, 1.20, 0.006)
_PRO_OFF_PEAK = (0.66, 1.98, 0.022)
_PRO_PEAK = (1.32, 3.96, 0.044)

PRICES = {
    "deepseek-v4.1-flash": {"off": _OFF_PEAK, "peak": _FLASH_PEAK},
    "deepseek-v4-flash": {"off": _OFF_PEAK, "peak": _FLASH_PEAK},
    "deepseek-v4-pro": {"off": _PRO_OFF_PEAK, "peak": _PRO_PEAK},
    "deepseek-v4-flash-vision-exp": {"off": _OFF_PEAK, "peak": _FLASH_PEAK},
}

# Retired model ids that were Go traffic under an older name.
ALIASES = {"deepseek-flash": "deepseek-v4.1-flash"}

GO_PROVIDER = "opencode-go"


@dataclass(frozen=True)
class Request:
    """One billable provider call."""

    timestamp: datetime.datetime
    provider: str
    model: str
    input: int
    output: int
    reasoning: int
    cache_read: int
    cache_write: int
    stored_cost: float


@dataclass(frozen=True)
class DayReport:
    """One UTC day of the report; every day in the range appears."""

    date: datetime.date
    requests: int = 0
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    go_reported: float = 0.0
    go_cost: float = 0.0

    @property
    def label(self) -> str:
        return self.date.strftime("%m/%d")


@dataclass(frozen=True)
class Report:
    """The per-day report over an inclusive date range."""

    days: tuple[DayReport, ...]

    def day(self, label: str) -> DayReport:
        for entry in self.days:
            if entry.label == label:
                return entry
        raise KeyError(f"No day {label} in report")


@dataclass
class _Bucket:
    requests: int = 0
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    go_reported: float = 0.0
    go_cost: float = 0.0


def parse_requests(text: str) -> list[Request]:
    """Parse a ``;``-separated requests value into requests."""
    if not text.strip():
        return []
    return [_parse_request(part) for part in text.split(";")]


def _parse_request(text: str) -> Request:
    timestamp, provider, model, *tokens = text.split(",")
    input_value, output, reasoning, cache_read, cache_write, stored_cost = tokens
    return Request(
        timestamp=datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M").replace(
            tzinfo=datetime.timezone.utc
        ),
        provider=provider,
        model=model,
        input=int(input_value),
        output=int(output),
        reasoning=int(reasoning),
        cache_read=int(cache_read),
        cache_write=int(cache_write),
        stored_cost=float(stored_cost),
    )


def is_peak(timestamp: datetime.datetime) -> bool:
    """Mon-Fri 01:00-04:00 and 06:00-10:00 UTC; everything else is off-peak."""
    hour = timestamp.hour
    return timestamp.weekday() < 5 and (1 <= hour < 4 or 6 <= hour < 10)


def _rates(model: str, peak: bool) -> tuple[float, float, float] | None:
    price = PRICES.get(ALIASES.get(model, model))
    if price is None:
        return None
    return price["peak"] if peak else price["off"]


def is_go_priced(request: Request) -> bool:
    """True when the request is Go traffic at a model that has a price."""
    return request.provider == GO_PROVIDER and _rates(request.model, False) is not None


def request_cost(request: Request) -> float:
    """Peak-aware USD for one request; zero when it is not Go-priced."""
    if not is_go_priced(request):
        return 0.0
    input_rate, output_rate, cache_rate = _rates(
        request.model, is_peak(request.timestamp)
    )
    return (
        request.input * input_rate
        + (request.output + request.reasoning) * output_rate
        + request.cache_read * cache_rate
    ) / 1e6


def _accumulate(bucket: _Bucket, request: Request) -> None:
    bucket.requests += 1
    bucket.input += request.input
    bucket.output += request.output + request.reasoning
    bucket.cache_read += request.cache_read
    bucket.cache_write += request.cache_write
    if is_go_priced(request):
        bucket.go_reported += request.stored_cost
        bucket.go_cost += request_cost(request)


def _resolve_range(
    requests: list[Request],
    start: datetime.date | None,
    end: datetime.date | None,
) -> tuple[datetime.date, datetime.date] | None:
    """The inclusive range, from explicit bounds or the request days.

    Returns ``None`` when a bound is missing and there are no requests.
    """
    if start is not None and end is not None:
        return start, end
    if not requests:
        return None
    days = [request.timestamp.date() for request in requests]
    return start or min(days), end or max(days)


def _bucket_by_day(
    start: datetime.date, end: datetime.date
) -> dict[datetime.date, _Bucket]:
    """One empty bucket per day in the inclusive range."""
    buckets: dict[datetime.date, _Bucket] = {}
    cursor = start
    while cursor <= end:
        buckets[cursor] = _Bucket()
        cursor += datetime.timedelta(days=1)
    return buckets


def _accumulate_all(
    buckets: dict[datetime.date, _Bucket], requests: list[Request]
) -> None:
    """Add each request to its own day, ignoring days outside the range."""
    for request in requests:
        bucket = buckets.get(request.timestamp.date())
        if bucket is not None:
            _accumulate(bucket, request)


def _to_report(buckets: dict[datetime.date, _Bucket]) -> Report:
    """Render the buckets in day order."""
    days = tuple(
        DayReport(date=day, **vars(bucket))
        for day, bucket in sorted(buckets.items())
    )
    return Report(days=days)


def build_report(
    requests: list[Request],
    start: datetime.date | None = None,
    end: datetime.date | None = None,
) -> Report:
    """Bucket requests by day over an inclusive range.

    Without an explicit range, the range runs from the first through the last
    request day. Every day in the range is reported, including empty ones.
    """
    bounds = _resolve_range(requests, start, end)
    if bounds is None:
        return Report(days=())
    buckets = _bucket_by_day(*bounds)
    _accumulate_all(buckets, requests)
    return _to_report(buckets)
