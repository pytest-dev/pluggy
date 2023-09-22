from typing import List

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
    out: List[str] = []
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

    trace_out: List[str] = []
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

    trace_out: List[str] = []
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
