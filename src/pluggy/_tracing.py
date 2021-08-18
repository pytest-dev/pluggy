"""
Tracing utils
"""
from typing import Tuple, Callable, Dict, Optional, Union

TAGS = Tuple[str, ...]
ARGS = Tuple[object, ...]
PROCESSOR = Callable[[TAGS, ARGS], None]
WRITER = Optional[Callable[[str], None]]


class TagTracer:
    indent: int
    _tags2proc: Dict[TAGS, PROCESSOR]
    _writer: WRITER

    def __init__(self) -> None:
        self._tags2proc = {}
        self._writer = None
        self.indent = 0

    def get(self, name: str) -> "TagTracerSub":
        return TagTracerSub(self, (name,))

    def _format_message(self, tags: TAGS, args: ARGS) -> str:
        if isinstance(args[-1], dict):
            extra = args[-1]
            args = args[:-1]
        else:
            extra = {}

        content = " ".join(map(str, args))
        indent = "  " * self.indent

        lines = ["{}{} [{}]\n".format(indent, content, ":".join(tags))]

        for name, value in extra.items():
            lines.append(f"{indent}    {name}: {value}\n")

        return "".join(lines)

    def _processmessage(self, tags: TAGS, args: ARGS) -> None:
        if self._writer is not None and args:
            self._writer(self._format_message(tags, args))
        try:
            processor = self._tags2proc[tags]
        except KeyError:
            pass
        else:
            processor(tags, args)

    def setwriter(self, writer: WRITER) -> None:
        self._writer = writer

    def setprocessor(self, tags: Union[TAGS, str], processor: PROCESSOR) -> None:
        if isinstance(tags, str):
            tags = tuple(tags.split(":"))
        else:
            assert isinstance(tags, tuple)
        self._tags2proc[tags] = processor


class TagTracerSub:
    root: TagTracer
    tags: TAGS

    def __init__(self, root: TagTracer, tags: TAGS) -> None:
        self.root = root
        self.tags = tags

    def __call__(self, *args: object) -> None:
        self.root._processmessage(self.tags, args)

    def get(self, name: str) -> "TagTracerSub":
        return self.__class__(self.root, self.tags + (name,))
