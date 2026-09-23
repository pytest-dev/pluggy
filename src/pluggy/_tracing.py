"""Utilities for writing and processing trace messages."""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Sequence
from typing import Any
from typing import Final
from typing import TypeAlias


_Writer: TypeAlias = Callable[[str], object]
_Processor: TypeAlias = Callable[[tuple[str, ...], tuple[Any, ...]], object]


class TagTracer:
    """A root tracer for messages tagged with a hierarchy of names."""

    def __init__(self) -> None:
        """:meta private:"""
        self._tags2proc: dict[tuple[str, ...], _Processor] = {}
        self._writer: _Writer | None = None
        #: The indent level to use for messages (can be changed).
        self.indent: int = 0

    def get(self, name: str) -> TagTracerSub:
        """Return a tracer that adds ``name`` to each message's tags."""
        return TagTracerSub(self, (name,))

    def _format_message(self, tags: Sequence[str], args: Sequence[object]) -> str:
        if isinstance(args[-1], dict):
            extra = args[-1]
            args = args[:-1]
        else:
            extra = {}

        content = " ".join(map(str, args))
        indent = "  " * self.indent

        lines = [f"{indent}{content} [{':'.join(tags)}]\n"]

        for name, value in extra.items():
            lines.append(f"{indent}    {name}: {value}\n")

        return "".join(lines)

    def _processmessage(self, tags: tuple[str, ...], args: tuple[object, ...]) -> None:
        if self._writer is not None and args:
            self._writer(self._format_message(tags, args))
        if processor := self._tags2proc.get(tags):
            processor(tags, args)

    def setwriter(self, writer: _Writer | None) -> None:
        """Set the function that receives formatted trace messages.

        :param writer:
            A function ``writer(message)``. Pass ``None`` to disable writing
            messages. Initially not set.
        """
        self._writer = writer

    def setprocessor(self, tags: str | tuple[str, ...], processor: _Processor) -> None:
        """Set the processor for messages with exactly the given ``tags``.

        :param tags:
            A colon-separated string or a tuple of hierarchical tag names.
        :param processor:
            A callback ``processor(tags, args)`` called with the hierarchical
            tags tuple and message arguments tuple.
        """
        if isinstance(tags, str):
            tags = tuple(tags.split(":"))
        else:
            assert isinstance(tags, tuple)
        self._tags2proc[tags] = processor


class TagTracerSub:
    """A tracer that adds hierarchical tags to trace messages."""

    def __init__(self, root: TagTracer, tags: tuple[str, ...]) -> None:
        """:meta private:"""
        #: The shared root tracer.
        self.root: Final[TagTracer] = root
        #: The tags added to each message.
        self.tags: Final[tuple[str, ...]] = tags

    def __call__(self, *args: object) -> None:
        """Write a message with this tracer's tags."""
        self.root._processmessage(self.tags, args)

    def get(self, name: str) -> TagTracerSub:
        """Return a child tracer with ``name`` appended to its hierarchical
        tags."""
        return self.__class__(self.root, self.tags + (name,))
