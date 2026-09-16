"""TDD unit tests for the todo list domain."""

import pytest
from src.todo import TodoError, TodoList


def test_add_makes_a_todo_pending():
    todo = TodoList()
    todo.add("write the spec")
    assert todo.pending() == ["write the spec"]
    assert todo.completed() == []


def test_complete_moves_a_todo_out_of_pending():
    todo = TodoList()
    todo.add("write the spec")
    todo.complete("write the spec")
    assert todo.pending() == []
    assert todo.completed() == ["write the spec"]


def test_pending_preserves_insertion_order():
    todo = TodoList()
    todo.add("first")
    todo.add("second")
    assert todo.pending() == ["first", "second"]


def test_completing_an_unknown_todo_is_an_error():
    todo = TodoList()
    with pytest.raises(TodoError, match="unknown todo: missing"):
        todo.complete("missing")


def test_adding_a_blank_todo_is_an_error():
    todo = TodoList()
    with pytest.raises(TodoError, match="title must not be blank"):
        todo.add("   ")


def test_adding_a_duplicate_todo_is_an_error():
    todo = TodoList()
    todo.add("write the spec")
    with pytest.raises(TodoError, match="duplicate todo: write the spec"):
        todo.add("write the spec")
