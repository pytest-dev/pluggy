import pytest

from pluggy import HookimplMarker
from pluggy import HookspecMarker
from pluggy import PluginManager
from pluggy._tracing import TagTracer


hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


@pytest.fixture
def rootlogger() -> TagTracer:
    return TagTracer()


def test_simple(rootlogger: TagTracer) -> None:
    log = rootlogger.get("pytest")
    log("hello")
    out: list[str] = []
    rootlogger.setwriter(out.append)
    log("world")
    assert len(out) == 1
    assert out[0] == "world [pytest]\n"
    sublog = log.get("collection")
    sublog("hello")
    assert out[1] == "hello [pytest:collection]\n"


def test_indent(rootlogger: TagTracer) -> None:
    log = rootlogger.get("1")
    out = []
    log.root.setwriter(lambda arg: out.append(arg))
    log("hello")
    log.root.indent += 1
    log("line1")
    log("line2")
    log.root.indent += 1
    log("line3")
    log("line4")
    log.root.indent -= 1
    log("line5")
    log.root.indent -= 1
    log("last")
    assert len(out) == 7
    names = [x[: x.rfind(" [")] for x in out]
    assert names == [
        "hello",
        "  line1",
        "  line2",
        "    line3",
        "    line4",
        "  line5",
        "last",
    ]


def test_readable_output_dictargs(rootlogger: TagTracer) -> None:
    out = rootlogger._format_message(["test"], [1])
    assert out == "1 [test]\n"

    out2 = rootlogger._format_message(["test"], ["test", {"a": 1}])
    assert out2 == "test [test]\n    a: 1\n"


def test_setprocessor(rootlogger: TagTracer) -> None:
    log = rootlogger.get("1")
    log2 = log.get("2")
    assert log2.tags == tuple("12")
    out = []
    rootlogger.setprocessor(tuple("12"), lambda *args: out.append(args))
    log("not seen")
    log2("seen")
    assert len(out) == 1
    tags, args = out[0]
    assert "1" in tags
    assert "2" in tags
    assert args == ("seen",)
    l2 = []
    rootlogger.setprocessor("1:2", lambda *args: l2.append(args))
    log2("seen")
    tags, args = l2[0]
    assert args == ("seen",)


def test_plugin_tracing(pm: PluginManager) -> None:
    class Api:
        @hookspec
        def hello(self, arg: object) -> None:
            "api hook 1"

    pm.add_hookspecs(Api)
    hook = pm.hook
    test_hc = hook.hello

    class Plugin:
        @hookimpl
        def hello(self, arg):
            return arg + 1

    plugin = Plugin()

    trace_out: list[str] = []
    pm.trace.root.setwriter(trace_out.append)
    pm.register(plugin)
    pm.enable_tracing()

    out = test_hc(arg=3)
    assert out == [4]

    assert trace_out == [
        "  hello [hook]\n      arg: 3\n",
        "  finish hello --> [4] [hook]\n",
    ]


def test_dbl_plugin_tracing(pm: PluginManager) -> None:
    class Api:
        @hookspec
        def hello(self, arg: object) -> None:
            "api hook 1"

    pm.add_hookspecs(Api)
    hook = pm.hook
    test_hc = hook.hello

    class Plugin:
        @hookimpl
        def hello(self, arg):
            return arg + 1

        @hookimpl(specname="hello")
        def hello_again(self, arg):
            return arg + 100

    plugin = Plugin()

    trace_out: list[str] = []
    pm.trace.root.setwriter(trace_out.append)
    pm.register(plugin)
    pm.enable_tracing()

    out = test_hc(arg=3)
    assert out == [103, 4]

    assert trace_out == [
        "  hello [hook]\n      arg: 3\n",
        "  finish hello --> [103, 4] [hook]\n",
    ]

    trace_out.clear()
    pm.unregister(plugin)
    out = test_hc(arg=3)
    assert out == []

    assert trace_out == [
        "  hello [hook]\n      arg: 3\n",
        "  finish hello --> [] [hook]\n",
    ]


class BrokenRepr:
    def __repr__(self) -> str:
        raise RuntimeError("repr is broken")


class BrokenStr:
    def __str__(self) -> str:
        raise RuntimeError("str is broken")


class SurrogateRepr:
    def __repr__(self) -> str:
        return "\ud800"


def test_dictargs_keep_str_rendering(rootlogger: TagTracer) -> None:
    """Values keep their ``str`` rendering, the trace is a log not a repr dump."""
    out = rootlogger._format_message(["test"], ["call", {"name": "value", "n": 1}])
    assert out == "call [test]\n    name: value\n    n: 1\n"


def test_dictargs_escape_surrogate_values(rootlogger: TagTracer) -> None:
    out = rootlogger._format_message(["test"], ["test", {"arg": "\ud800"}])
    assert out == "test [test]\n    arg: \\ud800\n"
    out.encode()


def test_escape_surrogates_from_repr(rootlogger: TagTracer) -> None:
    """A surrogate coming out of the object's own repr is escaped too."""
    out = rootlogger._format_message(["test"], ["test", {"arg": SurrogateRepr()}])
    assert out == "test [test]\n    arg: \\ud800\n"
    out.encode()


def test_escape_surrogates_in_labels(rootlogger: TagTracer) -> None:
    out = rootlogger._format_message(["test"], ["\ud800"])
    assert out == "\\ud800 [test]\n"
    out.encode()


def test_non_ascii_values_are_kept(rootlogger: TagTracer) -> None:
    """Legible text is not mangled, only lone surrogates are escaped."""
    out = rootlogger._format_message(["test"], ["héllo", {"arg": "wörld"}])
    assert out == "héllo [test]\n    arg: wörld\n"
    out.encode()


def test_broken_repr_value_does_not_raise(rootlogger: TagTracer) -> None:
    out = rootlogger._format_message(["test"], ["test", {"arg": BrokenRepr()}])
    assert "RuntimeError('repr is broken') raised in str()" in out
    assert "BrokenRepr object at 0x" in out
    out.encode()


def test_broken_str_label_does_not_raise(rootlogger: TagTracer) -> None:
    out = rootlogger._format_message(["test"], [BrokenStr()])
    assert "RuntimeError('str is broken') raised in str()" in out
    assert "BrokenStr object at 0x" in out
    out.encode()


def test_keyboard_interrupt_from_str_propagates(rootlogger: TagTracer) -> None:
    """Ctrl-C during a traced call still interrupts, it is not swallowed."""

    class Interrupting:
        def __str__(self) -> str:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        rootlogger._format_message(["test"], ["test", {"arg": Interrupting()}])


def test_broken_exception_repr_is_handled(rootlogger: TagTracer) -> None:
    """The exception explaining the failure may itself be unpresentable."""

    class BadError(Exception):
        def __repr__(self) -> str:
            raise RuntimeError("exception repr is broken")

        def __str__(self) -> str:
            return "readable message"

    class Broken:
        def __str__(self) -> str:
            raise BadError

    out = rootlogger._format_message(["test"], ["test", {"arg": Broken()}])
    assert 'BadError("readable message") raised in str()' in out
    assert "Broken object at 0x" in out


def test_unpresentable_exception_is_handled(rootlogger: TagTracer) -> None:
    """Neither repr nor str of the exception works, and tracing still survives."""

    class UnpresentableError(Exception):
        def __repr__(self) -> str:
            raise RuntimeError("exception repr is broken")

        def __str__(self) -> str:
            raise RuntimeError("exception str is broken")

    class Broken:
        def __str__(self) -> str:
            raise UnpresentableError

    out = rootlogger._format_message(["test"], ["test", {"arg": Broken()}])
    assert "unpresentable exception (RuntimeError('exception str is broken'))" in out
    assert "Broken object at 0x" in out


def test_keyboard_interrupt_from_exception_repr_propagates(
    rootlogger: TagTracer,
) -> None:
    """Ctrl-C while rendering the failure explanation propagates as well."""

    class InterruptingError(Exception):
        def __repr__(self) -> str:
            raise KeyboardInterrupt

    class Broken:
        def __str__(self) -> str:
            raise InterruptingError

    with pytest.raises(KeyboardInterrupt):
        rootlogger._format_message(["test"], ["test", {"arg": Broken()}])
