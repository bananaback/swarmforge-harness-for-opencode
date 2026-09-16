"""Step handlers for the todo acceptance feature."""

import re

from runtime import World
from src.todo import TodoError, TodoList


def _todo(world: World) -> TodoList:
    return world.state["todo"]


def _quoted(examples: dict[str, str], pattern: str) -> str:
    text = examples.get("_step_text", "")
    match = re.match(pattern, text)
    assert match, f"step text did not match: {text!r}"
    return match.group(1)


def _titles(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _empty_list(world: World, examples: dict[str, str]) -> None:
    world.state["todo"] = TodoList()
    world.state["error"] = None


def _add_todo(world: World, examples: dict[str, str]) -> None:
    title = _quoted(examples, r'^I add the todo "([^"]*)"$')
    try:
        _todo(world).add(title)
    except TodoError as error:
        world.state["error"] = error


def _complete_todo(world: World, examples: dict[str, str]) -> None:
    title = _quoted(examples, r'^I complete the todo "([^"]*)"$')
    try:
        _todo(world).complete(title)
    except TodoError as error:
        world.state["error"] = error


def _pending_are(world: World, examples: dict[str, str]) -> None:
    value = _quoted(examples, r'^the pending todos are "([^"]*)"$')
    assert _todo(world).pending() == _titles(value)


def _completed_are(world: World, examples: dict[str, str]) -> None:
    value = _quoted(examples, r'^the completed todos are "([^"]*)"$')
    assert _todo(world).completed() == _titles(value)


def _no_pending(world: World, examples: dict[str, str]) -> None:
    assert _todo(world).pending() == []


def _operation_fails(world: World, examples: dict[str, str]) -> None:
    expected = _quoted(examples, r'^the operation fails with "([^"]*)"$')
    error = world.state.get("error")
    assert isinstance(error, TodoError), f"expected a TodoError, got {error!r}"
    assert str(error) == expected


HANDLERS = [
    (r"^an empty todo list$", _empty_list),
    (r'^I add the todo "[^"]*"$', _add_todo),
    (r'^I complete the todo "[^"]*"$', _complete_todo),
    (r'^the pending todos are "[^"]*"$', _pending_are),
    (r'^the completed todos are "[^"]*"$', _completed_are),
    (r"^there are no pending todos$", _no_pending),
    (r'^the operation fails with "[^"]*"$', _operation_fails),
]
