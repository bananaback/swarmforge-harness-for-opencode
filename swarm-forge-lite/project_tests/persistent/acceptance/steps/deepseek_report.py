"""Step handlers for the DeepSeek per-request report feature."""

import datetime
import re
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

from deepseek_report import build_report, parse_requests  # noqa: E402

_REQUEST_PREFIX = "the requests "
_RANGE = re.compile(r"covers (\d{4}-\d{2}-\d{2}) through (\d{4}-\d{2}-\d{2})")


def _requests_text(params):
    """The requests value, from the example or the literal step text."""
    value = params.get("requests")
    if value is not None:
        return value
    return params["_step_text"][len(_REQUEST_PREFIX):]


def _given_requests(world, params):
    world.state["requests"] = parse_requests(_requests_text(params))


def _given_range(world, params):
    match = _RANGE.search(params["_step_text"])
    world.state["start"] = datetime.date.fromisoformat(match.group(1))
    world.state["end"] = datetime.date.fromisoformat(match.group(2))


def _when_report(world, params):
    world.state["report"] = build_report(
        world.state["requests"],
        start=world.state.get("start"),
        end=world.state.get("end"),
    )


def _day(world, params):
    return world.state["report"].day(params["day"])


def _then_requests(world, params):
    assert _day(world, params).requests == int(params["requests_count"])


def _then_input(world, params):
    assert _day(world, params).input == int(params["input"])


def _then_output(world, params):
    assert _day(world, params).output == int(params["output"])


def _then_cache_read(world, params):
    assert _day(world, params).cache_read == int(params["cache_read"])


def _then_cache_write(world, params):
    assert _day(world, params).cache_write == int(params["cache_write"])


def _then_go_reported(world, params):
    assert round(_day(world, params).go_reported, 6) == float(params["go_reported"])


def _then_go_cost(world, params):
    assert round(_day(world, params).go_cost, 6) == float(params["go_cost"])


HANDLERS = [
    (r"^the requests .+$", _given_requests),
    (r"^the report covers \d{4}-\d{2}-\d{2} through \d{4}-\d{2}-\d{2}$", _given_range),
    (r"^the DeepSeek report is generated$", _when_report),
    (r"^the day <day> reports a request count of <requests_count>$", _then_requests),
    (r"^the day <day> reports <input> input tokens$", _then_input),
    (r"^the day <day> reports <output> output tokens$", _then_output),
    (r"^the day <day> reports <cache_read> cache read tokens$", _then_cache_read),
    (r"^the day <day> reports <cache_write> cache write tokens$", _then_cache_write),
    (
        r"^the day <day> reports Go-reported cost <go_reported> "
        r"rounded to 6 decimal places$",
        _then_go_reported,
    ),
    (
        r"^the day <day> reports peak-aware cost <go_cost> "
        r"rounded to 6 decimal places$",
        _then_go_cost,
    ),
]
