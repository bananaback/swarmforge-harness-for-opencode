"""Step handlers for the durable store acceptance feature.

Every handler calls ``durable_store`` directly: the feature pins the storage
primitives, not a CLI. The one CLI-shaped scenario exercises ``run_cli`` with a
stub command whose refusal carries the scenario's problems.
"""

import argparse
import io
import re
import threading
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone

import durable_store
from runtime import World

from .common import _temp_root, step_values

_STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_LOCK_POLL_SECONDS = 0.5
_LOCK_WAIT_SECONDS = 10


# --- iso_now ---------------------------------------------------------------


def _stamp_now(world: World, examples: dict[str, str]) -> None:
    world.state["stamp"] = durable_store.iso_now()


def _stamp_is_utc(world: World, examples: dict[str, str]) -> None:
    stamp = world.state["stamp"]
    assert _STAMP_RE.match(stamp), f"not a UTC stamp: {stamp!r}"


def _stamp_is_recent(world: World, examples: dict[str, str]) -> None:
    stamp = datetime.strptime(
        world.state["stamp"], "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=timezone.utc)
    age = abs((datetime.now(timezone.utc) - stamp).total_seconds())
    assert age < 60, f"stamp is {age:.1f}s from now"


# --- atomic write ----------------------------------------------------------


def _atomic_write(world: World, examples: dict[str, str]) -> None:
    directory = _temp_root() / "store"
    path = directory / "doc.json"
    document = {"b": [2, 1], "a": {"nested": True}}
    durable_store.write_json_atomic(path, document)
    world.state["document_path"] = path
    world.state["document"] = document


def _document_round_trips(world: World, examples: dict[str, str]) -> None:
    read_back = durable_store.read_json(world.state["document_path"])
    assert read_back == world.state["document"], read_back


def _no_temporary_file(world: World, examples: dict[str, str]) -> None:
    directory = world.state["document_path"].parent
    names = sorted(path.name for path in directory.iterdir())
    assert names == ["doc.json"], names


# --- list_json -------------------------------------------------------------


def _directory_holds(world: World, examples: dict[str, str]) -> None:
    (files,) = step_values(
        examples, r'^the durable store directory holds the files "([^"]*)"$'
    )
    directory = _temp_root() / "listing"
    directory.mkdir()
    for name in files.split(","):
        (directory / name).write_text("{}")
    world.state["listing_dir"] = directory


def _list_directory(world: World, examples: dict[str, str]) -> None:
    world.state["listing"] = durable_store.list_json(world.state["listing_dir"])


def _listing_is(world: World, examples: dict[str, str]) -> None:
    (expected,) = step_values(examples, r'^the listing is "([^"]*)"$')
    actual = ",".join(path.name for path in world.state["listing"])
    assert actual == expected, f"{actual!r} != {expected!r}"


# --- next_seq --------------------------------------------------------------


def _counter_starts(world: World, examples: dict[str, str]) -> None:
    (start,) = step_values(
        examples, r"^the durable store counter starts at (.+)$"
    )
    path = _temp_root() / "sequence.txt"
    path.write_text(f"{start}\n")
    world.state["sequence_path"] = path


def _allocate_sequences(world: World, examples: dict[str, str]) -> None:
    (calls,) = step_values(
        examples, r"^the durable store allocates (.+) sequence numbers$"
    )
    world.state["sequences"] = [
        durable_store.next_seq(world.state["sequence_path"])
        for _ in range(int(calls))
    ]


def _sequences_are(world: World, examples: dict[str, str]) -> None:
    (expected,) = step_values(
        examples, r'^the allocated sequence numbers are "([^"]*)"$'
    )
    actual = ",".join(str(value) for value in world.state["sequences"])
    assert actual == expected, f"{actual!r} != {expected!r}"


# --- lock ------------------------------------------------------------------


def _second_holder_requests(world: World, examples: dict[str, str]) -> None:
    requested, held = step_values(
        examples,
        r'^a second holder requests the lock "([^"]*)" while the store holds '
        r'the lock "([^"]*)"$',
    )
    lock_dir = _temp_root() / "locks"
    released = threading.Event()
    entered = threading.Event()

    def hold() -> None:
        with durable_store.lock(lock_dir, held):
            entered.set()
            released.wait(timeout=_LOCK_WAIT_SECONDS)

    holder = threading.Thread(target=hold)
    holder.start()
    assert entered.wait(timeout=_LOCK_WAIT_SECONDS), "holder never took the lock"

    def request() -> None:
        with durable_store.lock(lock_dir, requested):
            pass

    second = threading.Thread(target=request)
    second.start()
    second.join(timeout=_LOCK_POLL_SECONDS)
    world.state["second_blocked"] = second.is_alive()
    released.set()
    holder.join(timeout=_LOCK_WAIT_SECONDS)
    second.join(timeout=_LOCK_WAIT_SECONDS)


def _second_holder_outcome(world: World, examples: dict[str, str]) -> None:
    (outcome,) = step_values(examples, r"^the second holder (.+)$")
    blocked = world.state["second_blocked"]
    if outcome == "is blocked":
        assert blocked, "the second holder was admitted"
    elif outcome == "is admitted":
        assert not blocked, "the second holder was blocked"
    else:
        raise AssertionError(f"unknown outcome: {outcome}")


# --- run_cli ---------------------------------------------------------------


def _refusal_cli(problems: list[str]) -> tuple[int, str]:
    class ToolError(Exception):
        def __init__(self) -> None:
            super().__init__("tool error")
            self.problems = problems

    def refuse(args) -> None:
        raise ToolError()

    def build_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="tool")
        parser.add_argument("--root", default=".")
        parser.set_defaults(func=refuse)
        return parser

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = durable_store.run_cli(build_parser, ToolError, "TOOL", argv=[])
    return code, err.getvalue()


def _cli_refuses(world: World, examples: dict[str, str]) -> None:
    (problems,) = step_values(
        examples, r'^the durable store CLI refuses with the problems "([^"]*)"$'
    )
    code, stderr = _refusal_cli(problems.split(";"))
    world.state["cli_exit"] = code
    world.state["cli_stderr"] = stderr


def _cli_exits_with(world: World, examples: dict[str, str]) -> None:
    (exit_code,) = step_values(
        examples, r"^the durable store CLI exits with code (.+)$"
    )
    assert world.state["cli_exit"] == int(exit_code)


def _cli_problem_lines(world: World, examples: dict[str, str]) -> None:
    (lines,) = step_values(
        examples, r'^the durable store CLI prints the problem lines "([^"]*)"$'
    )
    actual = [
        line
        for line in world.state["cli_stderr"].splitlines()
        if line.startswith("- ")
    ]
    assert actual == lines.split(";"), f"{actual!r} != {lines.split(';')!r}"


HANDLERS = [
    (r"^the durable store stamps the current time$", _stamp_now),
    (r"^the stamp is a UTC timestamp in the documented format$", _stamp_is_utc),
    (r"^the stamp is close to the current time$", _stamp_is_recent),
    (r"^the durable store atomically writes a document$", _atomic_write),
    (r"^the written document reads back unchanged$", _document_round_trips),
    (r"^the document directory holds no temporary file$", _no_temporary_file),
    (
        r'^the durable store directory holds the files "([^"]*)"$',
        _directory_holds,
    ),
    (r"^the durable store lists the directory$", _list_directory),
    (r'^the listing is "([^"]*)"$', _listing_is),
    (r"^the durable store counter starts at (.+)$", _counter_starts),
    (r"^the durable store allocates (.+) sequence numbers$", _allocate_sequences),
    (r'^the allocated sequence numbers are "([^"]*)"$', _sequences_are),
    (
        r'^a second holder requests the lock "([^"]*)" while the store holds '
        r'the lock "([^"]*)"$',
        _second_holder_requests,
    ),
    (r"^the second holder (.+)$", _second_holder_outcome),
    (
        r'^the durable store CLI refuses with the problems "([^"]*)"$',
        _cli_refuses,
    ),
    (r"^the durable store CLI exits with code (.+)$", _cli_exits_with),
    (
        r'^the durable store CLI prints the problem lines "([^"]*)"$',
        _cli_problem_lines,
    ),
]
