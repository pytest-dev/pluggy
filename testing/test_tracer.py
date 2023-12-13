from typing import List

import pytest

from pluggy._tracing import saferepr, DEFAULT_REPR_MAX_SIZE
from pluggy._tracing import TagTracer


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

def test_saferepr_simple_repr():
    assert saferepr(1) == "1"
    assert saferepr(None) == "None"


def test_saferepr_maxsize():
    s = saferepr("x" * 50, maxsize=25)
    assert len(s) == 25
    expected = repr("x" * 10 + "..." + "x" * 10)
    assert s == expected


def test_saferepr_no_maxsize():
    text = "x" * DEFAULT_REPR_MAX_SIZE * 10
    s = saferepr(text, maxsize=None)
    expected = repr(text)
    assert s == expected


def test_saferepr_maxsize_error_on_instance():
    class A:
        def __repr__(self):
            raise ValueError("...")

    s = saferepr(("*" * 50, A()), maxsize=25)
    assert len(s) == 25
    assert s[0] == "(" and s[-1] == ")"


def test_saferepr_exceptions() -> None:
    class BrokenRepr:
        def __init__(self, ex):
            self.ex = ex

        def __repr__(self):
            raise self.ex

    class BrokenReprException(Exception):
        __str__ = None  # type: ignore[assignment]
        __repr__ = None  # type: ignore[assignment]

    assert "Exception" in saferepr(BrokenRepr(Exception("broken")))
    s = saferepr(BrokenReprException("really broken"))
    assert "TypeError" in s
    assert "TypeError" in saferepr(BrokenRepr("string"))

    none = None
    try:
        none()  # type: ignore[misc]
    except BaseException as exc:
        exp_exc = repr(exc)
    obj = BrokenRepr(BrokenReprException("omg even worse"))
    s2 = saferepr(obj)
    assert s2 == (
        "<[unpresentable exception ({!s}) raised in repr()] BrokenRepr object at 0x{:x}>".format(
            exp_exc, id(obj)
        )
    )


def test_saferepr_baseexception():
    """Test saferepr() with BaseExceptions, which includes pytest outcomes."""

    class RaisingOnStrRepr(BaseException):
        def __init__(self, exc_types):
            self.exc_types = exc_types

        def raise_exc(self, *args):
            try:
                self.exc_type = self.exc_types.pop(0)
            except IndexError:
                pass
            if hasattr(self.exc_type, "__call__"):
                raise self.exc_type(*args)
            raise self.exc_type

        def __str__(self):
            self.raise_exc("__str__")

        def __repr__(self):
            self.raise_exc("__repr__")

    class BrokenObj:
        def __init__(self, exc):
            self.exc = exc

        def __repr__(self):
            raise self.exc

        __str__ = __repr__

    baseexc_str = BaseException("__str__")
    obj = BrokenObj(RaisingOnStrRepr([BaseException]))
    assert saferepr(obj) == (
        "<[unpresentable exception ({!r}) "
        "raised in repr()] BrokenObj object at 0x{:x}>".format(baseexc_str, id(obj))
    )
    obj = BrokenObj(RaisingOnStrRepr([RaisingOnStrRepr([BaseException])]))
    assert saferepr(obj) == (
        "<[{!r} raised in repr()] BrokenObj object at 0x{:x}>".format(
            baseexc_str, id(obj)
        )
    )

    with pytest.raises(KeyboardInterrupt):
        saferepr(BrokenObj(KeyboardInterrupt()))

    with pytest.raises(SystemExit):
        saferepr(BrokenObj(SystemExit()))

    with pytest.raises(KeyboardInterrupt):
        saferepr(BrokenObj(RaisingOnStrRepr([KeyboardInterrupt])))

    with pytest.raises(SystemExit):
        saferepr(BrokenObj(RaisingOnStrRepr([SystemExit])))

    with pytest.raises(KeyboardInterrupt):
        print(saferepr(BrokenObj(RaisingOnStrRepr([BaseException, KeyboardInterrupt]))))

    with pytest.raises(SystemExit):
        saferepr(BrokenObj(RaisingOnStrRepr([BaseException, SystemExit])))


def test_saferepr_buggy_builtin_repr():
    # Simulate a case where a repr for a builtin raises.
    # reprlib dispatches by type name, so use "int".

    class int:
        def __repr__(self):
            raise ValueError("Buggy repr!")

    assert "Buggy" in saferepr(int())


def test_saferepr_big_repr():
    from _pytest._io.saferepr import SafeRepr

    assert len(saferepr(range(1000))) <= len("[" + SafeRepr(0).maxlist * "1000" + "]")


def test_saferepr_repr_on_newstyle() -> None:
    class Function:
        def __repr__(self):
            return "<%s>" % (self.name)  # type: ignore[attr-defined]

    assert saferepr(Function())


def test_saferepr_unicode():
    val = "£€"
    reprval = "'£€'"
    assert saferepr(val) == reprval


def test_saferepr_broken_getattribute():
    """saferepr() can create proper representations of classes with
    broken __getattribute__ (#7145)
    """

    class SomeClass:
        def __getattribute__(self, attr):
            raise RuntimeError

        def __repr__(self):
            raise RuntimeError

    assert saferepr(SomeClass()).startswith(
        "<[RuntimeError() raised in repr()] SomeClass object at 0x"
    )