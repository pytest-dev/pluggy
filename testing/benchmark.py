"""
Benchmarking and performance tests.
"""
import pytest

from pluggy import _MultiCall, HookImpl
from pluggy import HookspecMarker, HookimplMarker


hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


def MC(methods, kwargs, firstresult=False):
    hookfuncs = []
    for method in methods:
        f = HookImpl(None, "<temp>", method, method.example_impl)
        hookfuncs.append(f)
    return _MultiCall(hookfuncs, kwargs, {"firstresult": firstresult})


@hookimpl(hookwrapper=True)
def m1(arg1, arg2, arg3):
    yield


@hookimpl
def m2(arg1, arg2, arg3):
    return arg1, arg2, arg3


@hookimpl(hookwrapper=True)
def w1(arg1, arg2, arg3):
    yield


@hookimpl(hookwrapper=True)
def w2(arg1, arg2, arg3):
    yield


def inner_exec(methods):
    return MC(methods, {'arg1': 1, 'arg2': 2, 'arg3': 3}).execute()


@pytest.mark.benchmark
def test_hookimpls_speed(benchmark):
    benchmark(inner_exec, [m1, m2])


@pytest.mark.benchmark
def test_hookwrappers_speed(benchmark):
    benchmark(inner_exec, [w1, w2])


@pytest.mark.benchmark
def test_impls_and_wrappers_speed(benchmark):
    benchmark(inner_exec, [m1, m2, w1, w2])
