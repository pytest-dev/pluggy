"""Utilities for writing and processing trace messages."""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Sequence
from typing import Any
from typing import Final
from typing import TypeAlias


_Writer: TypeAlias = Callable[[str], object]
_Processor: TypeAlias = Callable[[tuple[str, ...], tuple[Any, ...]], object]


def _describe_str_failure(exc: Exception, obj: object) -> str:
    try:
        exc_info = repr(exc)
    except Exception:
        exc_info = f"unpresentable {type(exc).__name__}"
    name = type(obj).__name__
    return f"<[{exc_info} raised in str()] {name} object at 0x{id(obj):x}>"


def _escape_surrogates(text: str) -> str:
    """Escape lone surrogates so the result survives any text writer.

    A lone surrogate reaching the writer raises :exc:`UnicodeEncodeError`
    inside the trace call for any utf-8 target, such as the file behind
    pytest's ``--debug``.
    """
    if text.isascii():
        return text
    return text.encode("utf-8", "backslashreplace").decode("utf-8")


def _safe_str(obj: object) -> str:
    """``str(obj)`` for tracing, with a failing ``__str__`` rendered, not raised.

    The result has lone surrogates escaped, so any text writer accepts it.
    """
    try:
        text = str(obj)
    except Exception as exc:
        text = _describe_str_failure(exc, obj)
    return _escape_surrogates(text)


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

        content = " ".join(map(_safe_str, args))
        indent = "  " * self.indent

        lines = [f"{indent}{content} [{':'.join(tags)}]\n"]

        for name, value in extra.items():
            lines.append(f"{indent}    {name}: {_safe_str(value)}\n")

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
