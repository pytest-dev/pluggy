"""
Tracing utils
"""
from .callers import _Result

if False:  # TYPE_CHECKING
    from typing import Any
    from typing import Callable
    from typing import Dict
    from typing import List
    from typing import Optional
    from typing import Sequence
    from typing import Tuple
    from typing import Union

    from .hooks import HookImpl
    from .hooks import _HookCaller
    from .manager import PluginManager

    _Writer = Callable[[str], None]
    _Processor = Callable[[Tuple[str, ...], Sequence[object]], None]
    _BeforeTrace = Callable[[str, List[HookImpl], Dict[str, Any]], None]
    _AfterTrace = Callable[[_Result[Any], str, List[HookImpl], Dict[str, Any]], None]


class TagTracer(object):
    def __init__(self):
        # type: () -> None
        self._tag2proc = {}  # type: Dict[Tuple[str, ...], _Processor]
        self.writer = None  # type: Optional[_Writer]
        self.indent = 0

    def get(self, name):
        # type: (str) -> TagTracerSub
        return TagTracerSub(self, (name,))

    def format_message(self, tags, args):
        # type: (Sequence[str], Sequence[object]) -> List[str]
        if isinstance(args[-1], dict):
            extra = args[-1]
            args = args[:-1]
        else:
            extra = {}

        content = " ".join(map(str, args))
        indent = "  " * self.indent

        lines = ["%s%s [%s]\n" % (indent, content, ":".join(tags))]

        for name, value in extra.items():
            lines.append("%s    %s: %s\n" % (indent, name, value))
        return lines

    def processmessage(self, tags, args):
        # type: (Tuple[str, ...], Sequence[object]) -> None
        if self.writer is not None and args:
            lines = self.format_message(tags, args)
            self.writer("".join(lines))
        try:
            self._tag2proc[tags](tags, args)
        except KeyError:
            pass

    def setwriter(self, writer):
        # type: (_Writer) -> None
        self.writer = writer

    def setprocessor(self, tags, processor):
        # type: (Union[str, Tuple[str, ...]], _Processor) -> None
        if isinstance(tags, str):
            tags = tuple(tags.split(":"))
        else:
            assert isinstance(tags, tuple)
        self._tag2proc[tags] = processor


class TagTracerSub(object):
    def __init__(self, root, tags):
        # type: (TagTracer, Tuple[str, ...]) -> None
        self.root = root
        self.tags = tags

    def __call__(self, *args):
        # type: (object) -> None
        self.root.processmessage(self.tags, args)

    def setmyprocessor(self, processor):
        # type: (_Processor) -> None
        self.root.setprocessor(self.tags, processor)

    def get(self, name):
        # type: (str) -> TagTracerSub
        return self.__class__(self.root, self.tags + (name,))


class _TracedHookExecution(object):
    def __init__(self, pluginmanager, before, after):
        # type: (PluginManager, _BeforeTrace, _AfterTrace) -> None
        self.pluginmanager = pluginmanager
        self.before = before
        self.after = after
        self.oldcall = pluginmanager._inner_hookexec
        assert not isinstance(self.oldcall, _TracedHookExecution)
        self.pluginmanager._inner_hookexec = self

    def __call__(self, hook, methods, kwargs):
        # type: (_HookCaller, List[HookImpl], Dict[str, object]) -> Union[object, List[object]]
        self.before(hook.name, methods, kwargs)
        outcome = _Result.from_call(lambda: self.oldcall(hook, methods, kwargs))
        self.after(outcome, hook.name, methods, kwargs)
        return outcome.get_result()

    def undo(self):
        # type: () -> None
        self.pluginmanager._inner_hookexec = self.oldcall
