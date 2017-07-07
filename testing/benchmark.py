"""
Benchmarking and performance tests.
"""
import pytest
from pluggy import _MultiCall, HookImpl, HookspecMarker, HookimplMarker

hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


def MC(methods, kwargs, firstresult=False):
    hookfuncs = []
    for method in methods:
        f = HookImpl(None, "<temp>", method, method.example_impl)
        hookfuncs.append(f)
    return _MultiCall(hookfuncs, kwargs, {"firstresult": firstresult})


@hookimpl
def hook(arg1, arg2, arg3):
    return arg1, arg2, arg3


@hookimpl(hookwrapper=True)
def wrapper(arg1, arg2, arg3):
    yield


@pytest.fixture(
    params=[0, 1, 10, 100],
    ids="hooks={}".format,
)
def hooks(request):
    return [hook for i in range(request.param)]


@pytest.fixture(
    params=[0, 1, 10, 100],
    ids="wrappers={}".format,
)
def wrappers(request):
    return [wrapper for i in range(request.param)]


def inner_exec(methods):
    return MC(methods, {'arg1': 1, 'arg2': 2, 'arg3': 3}).execute()


def test_hook_and_wrappers_speed(benchmark, hooks, wrappers):
    benchmark(inner_exec, hooks + wrappers)
