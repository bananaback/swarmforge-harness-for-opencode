"""A tiny in-memory todo list domain."""

from dataclasses import dataclass, field


class TodoError(Exception):
    """Raised when a todo operation is invalid."""


@dataclass
class TodoList:
    """An ordered set of todo titles, each pending or completed."""

    _items: dict[str, bool] = field(default_factory=dict)

    def add(self, title: str) -> None:
        """Add ``title`` as a pending todo; reject a blank or duplicate title."""
        if not title or not title.strip():
            raise TodoError("title must not be blank")
        if title in self._items:
            raise TodoError(f"duplicate todo: {title}")
        self._items[title] = False

    def complete(self, title: str) -> None:
        """Mark ``title`` completed; reject an unknown title."""
        if title not in self._items:
            raise TodoError(f"unknown todo: {title}")
        self._items[title] = True

    def pending(self) -> list[str]:
        """Return the pending titles in insertion order."""
        return [title for title, done in self._items.items() if not done]

    def completed(self) -> list[str]:
        """Return the completed titles in insertion order."""
        return [title for title, done in self._items.items() if done]
