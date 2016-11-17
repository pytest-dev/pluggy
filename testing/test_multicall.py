import pytest

from pluggy import _MultiCall, HookImpl, HookCallError
from pluggy import HookspecMarker, HookimplMarker


hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


def test_uses_copy_of_methods():
    l = [lambda: 42]
    mc = _MultiCall(l, {})
    repr(mc)
    l[:] = []
    res = mc.execute()
    return res == 42


def MC(methods, kwargs, firstresult=False):
    hookfuncs = []
    for method in methods:
        f = HookImpl(None, "<temp>", method, method.example_impl)
        hookfuncs.append(f)
    return _MultiCall(hookfuncs, kwargs, firstresult=firstresult)


def test_call_passing():
    class P1(object):
        @hookimpl
        def m(self, __multicall__, x):
            assert len(__multicall__.results) == 1
            assert not __multicall__.hook_impls
            return 17

    class P2(object):
        @hookimpl
        def m(self, __multicall__, x):
            assert __multicall__.results == []
            assert __multicall__.hook_impls
            return 23

    p1 = P1()
    p2 = P2()
    multicall = MC([p1.m, p2.m], {"x": 23})
    assert "23" in repr(multicall)
    reslist = multicall.execute()
    assert len(reslist) == 2
    # ensure reversed order
    assert reslist == [23, 17]


def test_keyword_args():
    @hookimpl
    def f(x):
        return x + 1

    class A(object):
        @hookimpl
        def f(self, x, y):
            return x + y

    multicall = MC([f, A().f], dict(x=23, y=24))
    assert "'x': 23" in repr(multicall)
    assert "'y': 24" in repr(multicall)
    reslist = multicall.execute()
    assert reslist == [24 + 23, 24]
    assert "2 results" in repr(multicall)


def test_keyword_args_with_defaultargs():
    @hookimpl
    def f(x, z=1):
        return x + z
    reslist = MC([f], dict(x=23, y=24)).execute()
    assert reslist == [24]


def test_tags_call_error():
    @hookimpl
    def f(x):
        return x
    multicall = MC([f], {})
    pytest.raises(HookCallError, multicall.execute)


def test_call_subexecute():
    @hookimpl
    def m(__multicall__):
        subresult = __multicall__.execute()
        return subresult + 1

    @hookimpl
    def n():
        return 1

    call = MC([n, m], {}, firstresult=True)
    res = call.execute()
    assert res == 2


def test_call_none_is_no_result():
    @hookimpl
    def m1():
        return 1

    @hookimpl
    def m2():
        return None

    res = MC([m1, m2], {}, {"firstresult": True}).execute()
    assert res == 1
    res = MC([m1, m2], {}, {}).execute()
    assert res == [1]


def test_hookwrapper():
    l = []

    @hookimpl(hookwrapper=True)
    def m1():
        l.append("m1 init")
        yield None
        l.append("m1 finish")

    @hookimpl
    def m2():
        l.append("m2")
        return 2

    res = MC([m2, m1], {}).execute()
    assert res == [2]
    assert l == ["m1 init", "m2", "m1 finish"]
    l[:] = []
    res = MC([m2, m1], {}, {"firstresult": True}).execute()
    assert res == 2
    assert l == ["m1 init", "m2", "m1 finish"]


def test_hookwrapper_order():
    l = []

    @hookimpl(hookwrapper=True)
    def m1():
        l.append("m1 init")
        yield 1
        l.append("m1 finish")

    @hookimpl(hookwrapper=True)
    def m2():
        l.append("m2 init")
        yield 2
        l.append("m2 finish")

    res = MC([m2, m1], {}).execute()
    assert res == []
    assert l == ["m1 init", "m2 init", "m2 finish", "m1 finish"]


def test_hookwrapper_not_yield():
    @hookimpl(hookwrapper=True)
    def m1():
        pass

    mc = MC([m1], {})
    with pytest.raises(TypeError):
        mc.execute()


def test_hookwrapper_too_many_yield():
    @hookimpl(hookwrapper=True)
    def m1():
        yield 1
        yield 2

    mc = MC([m1], {})
    with pytest.raises(RuntimeError) as ex:
        mc.execute()
    assert "m1" in str(ex.value)
    assert (__file__ + ':') in str(ex.value)


@pytest.mark.parametrize("exc", [ValueError, SystemExit])
def test_hookwrapper_exception(exc):
    l = []

    @hookimpl(hookwrapper=True)
    def m1():
        l.append("m1 init")
        yield None
        l.append("m1 finish")

    @hookimpl
    def m2():
        raise exc

    with pytest.raises(exc):
        MC([m2, m1], {}).execute()
    assert l == ["m1 init", "m1 finish"]
