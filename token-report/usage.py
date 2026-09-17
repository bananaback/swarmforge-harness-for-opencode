"""Token-usage domain calculations for OpenCode sessions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    input: int = 0
    output: int = 0
    reasoning: int = 0
    cache_read: int = 0
    cache_write: int = 0
    cost: float = 0.0
    requests: int = 0


@dataclass(frozen=True)
class Usage:
    total_input: int
    total_output: int
    cache_hit: float
    output_ratio: float
    cost: float


@dataclass(frozen=True)
class Summary:
    sessions: int
    requests: int
    input: int
    output: int
    reasoning: int
    cache_read: int
    cache_write: int
    total_input: int
    total_output: int
    cache_hit: float
    output_ratio: float
    cost: float


def _totals(
    input_tokens: int, output_tokens: int, reasoning: int, cache_read: int
) -> tuple[int, int]:
    """Total input adds cache read; total output adds reasoning."""
    return input_tokens + cache_read, output_tokens + reasoning


def _ratios(cache_read: int, total_output: int, total_input: int) -> tuple[float, float]:
    """Cache hit and output ratio, both zero when there is no input."""
    if total_input > 0:
        return cache_read / total_input, total_output / total_input
    return 0, 0


def session_usage(session: Session) -> Usage:
    """Calculate the token usage of a single session."""
    total_input, total_output = _totals(
        session.input, session.output, session.reasoning, session.cache_read
    )
    cache_hit, output_ratio = _ratios(session.cache_read, total_output, total_input)
    return Usage(
        total_input=total_input,
        total_output=total_output,
        cache_hit=cache_hit,
        output_ratio=output_ratio,
        cost=session.cost,
    )


def parse_sessions(text: str) -> list[Session]:
    """Parse a ``;``-separated sessions value into sessions."""
    if not text.strip():
        return []
    return [_parse_session(part) for part in text.split(";")]


def _parse_session(text: str) -> Session:
    input_value, output, reasoning, cache_read, cache_write, cost, requests = (
        text.split(",")
    )
    return Session(
        input=int(input_value),
        output=int(output),
        reasoning=int(reasoning),
        cache_read=int(cache_read),
        cache_write=int(cache_write),
        cost=float(cost),
        requests=int(requests),
    )


def summarize(sessions: list[Session]) -> Summary:
    """Aggregate a list of sessions into one summary."""
    input_total = sum(session.input for session in sessions)
    output_total = sum(session.output for session in sessions)
    reasoning_total = sum(session.reasoning for session in sessions)
    cache_read_total = sum(session.cache_read for session in sessions)
    cache_write_total = sum(session.cache_write for session in sessions)
    cost_total = sum(session.cost for session in sessions)
    requests = sum(session.requests for session in sessions)
    total_input, total_output = _totals(
        input_total, output_total, reasoning_total, cache_read_total
    )
    cache_hit, output_ratio = _ratios(cache_read_total, total_output, total_input)
    return Summary(
        sessions=len(sessions),
        requests=requests,
        input=input_total,
        output=output_total,
        reasoning=reasoning_total,
        cache_read=cache_read_total,
        cache_write=cache_write_total,
        total_input=total_input,
        total_output=total_output,
        cache_hit=cache_hit,
        output_ratio=output_ratio,
        cost=cost_total,
    )
