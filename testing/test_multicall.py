from typing import Callable, Mapping, List, Sequence, Type, Union

import pytest
from pluggy import HookCallError, HookspecMarker, HookimplMarker
from pluggy._hooks import HookImpl
from pluggy._callers import _multicall


hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


def MC(
    methods: Sequence[Callable[..., object]],
    kwargs: Mapping[str, object],
    firstresult: bool = False,
) -> Union[object, List[object]]:
    caller = _multicall
    hookfuncs = []
    for method in methods:
        f = HookImpl(None, "<temp>", method, method.example_impl)  # type: ignore[attr-defined]
        hookfuncs.append(f)
    return caller("foo", hookfuncs, kwargs, firstresult)


def test_keyword_args() -> None:
    @hookimpl
    def f(x):
        return x + 1

    class A:
        @hookimpl
        def f(self, x, y):
            return x + y

    reslist = MC([f, A().f], dict(x=23, y=24))
    assert reslist == [24 + 23, 24]


def test_keyword_args_with_defaultargs() -> None:
    @hookimpl
    def f(x, z=1):
        return x + z

    reslist = MC([f], dict(x=23, y=24))
    assert reslist == [24]


def test_tags_call_error() -> None:
    @hookimpl
    def f(x):
        return x

    with pytest.raises(HookCallError):
        MC([f], {})


def test_call_none_is_no_result() -> None:
    @hookimpl
    def m1():
        return 1

    @hookimpl
    def m2():
        return None

    res = MC([m1, m2], {}, firstresult=True)
    assert res == 1
    res = MC([m1, m2], {}, firstresult=False)
    assert res == [1]


def test_hookwrapper() -> None:
    out = []

    @hookimpl(hookwrapper=True)
    def m1():
        out.append("m1 init")
        yield None
        out.append("m1 finish")

    @hookimpl
    def m2():
        out.append("m2")
        return 2

    res = MC([m2, m1], {})
    assert res == [2]
    assert out == ["m1 init", "m2", "m1 finish"]
    out[:] = []
    res = MC([m2, m1], {}, firstresult=True)
    assert res == 2
    assert out == ["m1 init", "m2", "m1 finish"]


def test_hookwrapper_order() -> None:
    out = []

    @hookimpl(hookwrapper=True)
    def m1():
        out.append("m1 init")
        yield 1
        out.append("m1 finish")

    @hookimpl(hookwrapper=True)
    def m2():
        out.append("m2 init")
        yield 2
        out.append("m2 finish")

    res = MC([m2, m1], {})
    assert res == []
    assert out == ["m1 init", "m2 init", "m2 finish", "m1 finish"]


def test_hookwrapper_not_yield() -> None:
    @hookimpl(hookwrapper=True)
    def m1():
        pass

    with pytest.raises(TypeError):
        MC([m1], {})


def test_hookwrapper_too_many_yield() -> None:
    @hookimpl(hookwrapper=True)
    def m1():
        yield 1
        yield 2

    with pytest.raises(RuntimeError) as ex:
        MC([m1], {})
    assert "m1" in str(ex.value)
    assert (__file__ + ":") in str(ex.value)


@pytest.mark.parametrize("exc", [ValueError, SystemExit])
def test_hookwrapper_exception(exc: "Type[BaseException]") -> None:
    out = []

    @hookimpl(hookwrapper=True)
    def m1():
        out.append("m1 init")
        yield None
        out.append("m1 finish")

    @hookimpl
    def m2():
        raise exc

    with pytest.raises(exc):
        MC([m2, m1], {})
    assert out == ["m1 init", "m1 finish"]


def test_unwind_inner_wrapper_teardown_exc() -> None:
    out = []

    @hookimpl(hookwrapper=True)
    def m1():
        out.append("m1 init")
        try:
            outcome = yield 1
            out.append("m1 teardown")
            outcome.get_result()
            out.append("m1 unreachable")
        finally:
            out.append("m1 cleanup")

    @hookimpl(hookwrapper=True)
    def m2():
        out.append("m2 init")
        yield 2
        out.append("m2 raise")
        raise ValueError()

    with pytest.raises(ValueError):
        try:
            MC([m2, m1], {})
        finally:
            out.append("finally")

    assert out == [
        "m1 init",
        "m2 init",
        "m2 raise",
        "m1 teardown",
        "m1 cleanup",
        "finally",
    ]


def test_suppress_inner_wrapper_teardown_exc() -> None:
    out = []

    @hookimpl(hookwrapper=True)
    def m1():
        out.append("m1 init")
        outcome = yield 1
        outcome.get_result()
        out.append("m1 finish")

    @hookimpl(hookwrapper=True)
    def m2():
        out.append("m2 init")
        try:
            outcome = yield 2
            outcome.get_result()
            out.append("m2 unreachable")
        except ValueError:
            outcome.force_result(22)
            out.append("m2 suppress")

    @hookimpl(hookwrapper=True)
    def m3():
        out.append("m3 init")
        yield 3
        out.append("m3 raise")
        raise ValueError()

    assert 22 == MC([m3, m2, m1], {})
    assert out == [
        "m1 init",
        "m2 init",
        "m3 init",
        "m3 raise",
        "m2 suppress",
        "m1 finish",
    ]
