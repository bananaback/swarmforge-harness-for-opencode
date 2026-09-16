"""Property tests for the todo list domain."""

from hypothesis import given
from hypothesis import strategies as st
from src.todo import TodoList

TITLES = st.lists(
    st.text(min_size=1).filter(lambda text: text.strip()),
    min_size=1,
    unique=True,
    max_size=20,
)


@given(TITLES)
def test_completing_every_todo_leaves_none_pending(titles):
    todo = TodoList()
    for title in titles:
        todo.add(title)
    for title in titles:
        todo.complete(title)
    assert todo.pending() == []
    assert todo.completed() == titles


@given(TITLES)
def test_pending_and_completed_partition_the_todos(titles):
    todo = TodoList()
    for title in titles:
        todo.add(title)
    todo.complete(titles[0])
    assert sorted(todo.pending() + todo.completed()) == sorted(titles)
    assert titles[0] not in todo.pending()
