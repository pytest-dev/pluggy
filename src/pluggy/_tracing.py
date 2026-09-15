"""
Tracing utils
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Sequence
from typing import Any


_Writer = Callable[[str], object]
_Processor = Callable[[tuple[str, ...], tuple[Any, ...]], object]


def _try_repr_or_str(obj: object) -> str:
    try:
        return repr(obj)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:
        return f'{type(obj).__name__}("{obj}")'


def _format_str_exception(exc: BaseException, obj: object) -> str:
    try:
        exc_info = _try_repr_or_str(exc)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as inner:
        exc_info = f"unpresentable exception ({_try_repr_or_str(inner)})"
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
    """``str(obj)`` for tracing, guaranteed not to raise and always writable.

    Tracing is a debugging aid, so it must never be the reason a hook call
    fails, and the rendering stays ``str``-based to keep the trace output
    readable.
    """
    try:
        text = str(obj)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as exc:
        text = _format_str_exception(exc, obj)
    return _escape_surrogates(text)


class TagTracer:
    def __init__(self) -> None:
        self._tags2proc: dict[tuple[str, ...], _Processor] = {}
        self._writer: _Writer | None = None
        self.indent = 0

    def get(self, name: str) -> TagTracerSub:
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
        self._writer = writer

    def setprocessor(self, tags: str | tuple[str, ...], processor: _Processor) -> None:
        if isinstance(tags, str):
            tags = tuple(tags.split(":"))
        else:
            assert isinstance(tags, tuple)
        self._tags2proc[tags] = processor


class TagTracerSub:
    def __init__(self, root: TagTracer, tags: tuple[str, ...]) -> None:
        self.root = root
        self.tags = tags

    def __call__(self, *args: object) -> None:
        self.root._processmessage(self.tags, args)

    def get(self, name: str) -> TagTracerSub:
        return self.__class__(self.root, self.tags + (name,))
