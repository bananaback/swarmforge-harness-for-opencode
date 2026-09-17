"""Map database session rows to token-usage report dictionaries."""

from usage import Session, session_usage
from usage import summarize as summarize_usage


def stats(info: dict) -> dict:
    """Token usage for one database row dictionary."""
    usage = session_usage(
        Session(
            input=info['ti'], output=info['to'], reasoning=info['tr'],
            cache_read=info['tcr'], cache_write=info['tcw'], cost=info['cost'],
        )
    )
    return {
        'input': info['ti'], 'output': usage.total_output,
        'reasoning': info['tr'], 'cache_read': info['tcr'],
        'cache_hit': usage.cache_hit, 'output_ratio': usage.output_ratio,
        'total': info['ti'] + usage.total_output, 'cost': usage.cost,
    }


def summarize(sessions: list[dict]) -> dict:
    """Token-usage summary for database row dictionaries."""
    summary = summarize_usage([
        Session(
            input=s['ti'], output=s['to'], reasoning=s['tr'],
            cache_read=s['tcr'], cache_write=s['tcw'], cost=s['cost'],
            requests=s.get('requests', 0),
        )
        for s in sessions
    ])
    return {
        'sessions': summary.sessions, 'requests': summary.requests,
        'input': summary.input, 'output': summary.total_output,
        'reasoning': summary.reasoning, 'cache_read': summary.cache_read,
        'cache_write': summary.cache_write, 'total_input': summary.total_input,
        'cache_hit': summary.cache_hit, 'output_ratio': summary.output_ratio,
        'cost': summary.cost,
    }
