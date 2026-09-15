"""Step handlers for the deterministic mentor payload acceptance feature."""

import json
import os

import team
from runtime import World

from .common import (
    _project,
    _run_coder_team,
    _section_body,
    _task_json,
    _temp_harness,
)

_MENTOR_HEADERS = ("GOAL", "RULES", "TRAIL", "ASK", "FAILURE")

_DEFAULT_MENTOR_GOAL = "the default mentor goal"
_DEFAULT_MENTOR_RULES = "the default mentor rules"
_DEFAULT_MENTOR_ASK = "the default mentor ask"


def _bound_mentor_with_task(world: World, examples: dict[str, str]) -> None:
    """Background: open a mentor task with its chunk state and bind the mentor seat."""
    _temp_harness(world)
    world.state["task"] = "mentor-task"
    world.state["mentor_session"] = "mentor-1"
    world.state["worker_session"] = "worker-1"
    # the coder payload's stability handler reads these two keys
    world.state["session"] = "mentor-1"
    result = _run_coder_team(
        world, "open", "mentor-task", "--role", "mentor",
        "--goal", _DEFAULT_MENTOR_GOAL,
        "--rules", _DEFAULT_MENTOR_RULES,
        "--ask", _DEFAULT_MENTOR_ASK,
    )
    assert result.returncode == 0, f"open failed: {result.stderr}"
    result = _run_coder_team(
        world, "bind", "mentor-task", "--seat", "mentor", "--session", "mentor-1"
    )
    assert result.returncode == 0, f"bind mentor failed: {result.stderr}"
    result = _run_coder_team(
        world, "bind", "mentor-task", "--seat", "worker", "--session", "worker-1"
    )
    assert result.returncode == 0, f"bind worker failed: {result.stderr}"
    import datetime
    world.state["open_date"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")


def _mentor_calls_context(world: World, examples: dict[str, str]) -> None:
    result = _run_coder_team(
        world, "context", "--session", world.state["mentor_session"]
    )
    assert result.returncode == 0, f"context failed: {result.stderr}"
    world.state["payload"] = result.stdout


def _mentor_payload_headers(world: World) -> list[str]:
    known = set(_MENTOR_HEADERS)
    return [
        line.strip()
        for line in world.state["payload"].splitlines()
        if line.strip() in known
    ]


def _mentor_payload_section(world: World, header: str) -> str:
    return _section_body(world.state["payload"], _MENTOR_HEADERS, header)


def _payload_starts_with_system_prompt(world: World, examples: dict[str, str]) -> None:
    payload = world.state["payload"]
    assert payload.startswith(team.MENTOR_SYSTEM_PROMPT), (
        f"payload did not start with the system prompt: {payload[:80]!r}"
    )


def _payload_has_five_mentor_sections(world: World, examples: dict[str, str]) -> None:
    headers = _mentor_payload_headers(world)
    assert headers == list(_MENTOR_HEADERS), (
        f"expected 5 mentor sections in order, got {headers}"
    )


def _mentor_section_is(world: World, examples: dict[str, str]) -> None:
    position = int(examples["position"])
    headers = _mentor_payload_headers(world)
    assert headers[position - 1] == examples["section"], (
        f"section {position} was {headers[position - 1]!r}"
    )


def _chunk_state_sets(world: World, examples: dict[str, str]) -> None:
    path = _task_json(world)
    doc = json.loads(path.read_text())
    doc.setdefault("mentor", {})[examples["section"].lower()] = examples["value"]
    path.write_text(json.dumps(doc))


def _section_carries(world: World, examples: dict[str, str]) -> None:
    body = _mentor_payload_section(world, examples["section"])
    assert examples["value"] in body, (
        f"{examples['section']} section {body!r} lacks {examples['value']!r}"
    )


def _worker_journaled_plan_and_result(world: World, examples: dict[str, str]) -> None:
    session = world.state["worker_session"]
    for kind, marker in (
        ("plan", "mentor-trail-plan"),
        ("result", "mentor-trail-result"),
    ):
        result = _run_coder_team(
            world, "journal", "--session", session, "--kind", kind,
            "--entry", json.dumps({kind: marker}),
        )
        assert result.returncode == 0, f"journal failed: {result.stderr}"
        world.state[f"trail_{kind}"] = marker


def _trail_lists_both_in_order(world: World, examples: dict[str, str]) -> None:
    body = _mentor_payload_section(world, "TRAIL")
    plan = world.state["trail_plan"]
    result = world.state["trail_result"]
    assert plan in body and result in body, f"TRAIL section {body!r} lacks a marker"
    assert body.index(plan) < body.index(result), "TRAIL entries are out of order"


def _worker_records_failure(world: World, examples: dict[str, str]) -> None:
    evidence = examples["evidence"]
    result = _run_coder_team(
        world, "journal", "--session", world.state["worker_session"],
        "--kind", "stuck", "--entry", json.dumps({"failure": evidence}),
    )
    assert result.returncode == 0, f"journal failed: {result.stderr}"
    world.state["failure_evidence"] = evidence


def _failure_reproduces_evidence(world: World, examples: dict[str, str]) -> None:
    body = _mentor_payload_section(world, "FAILURE")
    evidence = world.state["failure_evidence"]
    assert body == evidence, f"FAILURE section {body!r} is not the evidence {evidence!r}"


def _model_stub_records_calls(world: World, examples: dict[str, str]) -> None:
    """Install a local recorder stub that would log any model request."""
    project = _project(world)
    stub = project / "model_stub.py"
    stub.write_text("import sys\nopen(sys.argv[1], 'a').write('call\\n')\n")
    os.environ["MENTOR_MODEL_STUB"] = str(stub)
    world.state["model_recorder"] = project / "model-calls.log"


def _no_model_request(world: World, examples: dict[str, str]) -> None:
    recorder = world.state["model_recorder"]
    assert not recorder.exists() or recorder.read_text() == "", (
        f"the model stub recorded a call: {recorder.read_text()!r}"
    )
    os.environ.pop("MENTOR_MODEL_STUB", None)


HANDLERS = [
    (r"^a bound mentor with a task and a chunk state$",
     _bound_mentor_with_task),
    (r"^the mentor calls team_context$",
     _mentor_calls_context),
    (r"^the payload starts with a system prompt$",
     _payload_starts_with_system_prompt),
    (r"^the payload has exactly 5 mentor sections$",
     _payload_has_five_mentor_sections),
    (r'^mentor section (\S+) is "([^"]*)"$',
     _mentor_section_is),
    (r'^the chunk state sets (\S+) to "([^"]*)"$',
     _chunk_state_sets),
    (r'^the "([^"]*)" section carries "([^"]*)"$',
     _section_carries),
    (r"^the worker journaled a plan and a result$",
     _worker_journaled_plan_and_result),
    (r"^the TRAIL section lists both journal entries in order$",
     _trail_lists_both_in_order),
    (r'^the worker recorded a failure with evidence "([^"]*)"$',
     _worker_records_failure),
    (r"^the FAILURE section reproduces the evidence verbatim$",
     _failure_reproduces_evidence),
    (r"^a model stub that records calls$",
     _model_stub_records_calls),
    (r"^no model request was made$",
     _no_model_request),
]
