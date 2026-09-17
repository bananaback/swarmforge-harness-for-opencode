"""Step handlers for the Token Usage feature."""

import sys
from pathlib import Path

_PACK_ROOT = Path(__file__).resolve().parents[4]
_TOOLS_ROOT = _PACK_ROOT / "tools" / "shared"
if str(_TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(_TOOLS_ROOT))

import wiring  # noqa: E402

_WORKSPACE_ROOT = wiring.load(environ={}).workspace_root
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))

from usage import Session, parse_sessions, session_usage, summarize  # noqa: E402


def _result(world):
    if "summary" in world.state:
        return world.state["summary"]
    return world.state["usage"]


def _given_session(world, params):
    world.state["session"] = Session(
        input=int(params["input"]),
        output=int(params["output"]),
        reasoning=int(params["reasoning"]),
        cache_read=int(params["cache_read"]),
        cache_write=int(params["cache_write"]),
        cost=float(params["cost"]),
    )


def _when_session_usage(world, params):
    world.state["usage"] = session_usage(world.state["session"])


def _given_sessions(world, params):
    world.state["sessions"] = parse_sessions(params["sessions"])


def _when_summarize(world, params):
    world.state["summary"] = summarize(world.state["sessions"])


def _then_total_input(world, params):
    assert _result(world).total_input == int(params["total_input"])


def _then_total_output(world, params):
    assert _result(world).total_output == int(params["total_output"])


def _then_cache_hit(world, params):
    assert round(_result(world).cache_hit, 6) == float(params["cache_hit"])


def _then_output_ratio(world, params):
    assert round(_result(world).output_ratio, 6) == float(params["output_ratio"])


def _then_cost(world, params):
    assert _result(world).cost == float(params["cost"])


def _then_session_count(world, params):
    assert world.state["summary"].sessions == int(params["session_count"])


def _then_request_count(world, params):
    assert world.state["summary"].requests == int(params["request_count"])


HANDLERS = [
    (
        r"^a session with input <input>, output <output>, reasoning <reasoning>, "
        r"cache read <cache_read>, cache write <cache_write>, and cost <cost>$",
        _given_session,
    ),
    (r"^the session's token usage is calculated$", _when_session_usage),
    (r"^the sessions <sessions>$", _given_sessions),
    (r"^the sessions are summarized$", _when_summarize),
    (r"^the total input is <total_input>$", _then_total_input),
    (r"^the total output is <total_output>$", _then_total_output),
    (
        r"^the cache hit ratio is <cache_hit> rounded to 6 decimal places$",
        _then_cache_hit,
    ),
    (
        r"^the output ratio is <output_ratio> rounded to 6 decimal places$",
        _then_output_ratio,
    ),
    (r"^the cost is <cost>$", _then_cost),
    (r"^the session count is <session_count>$", _then_session_count),
    (r"^the request count is <request_count>$", _then_request_count),
]
