"""
Benchmarking and performance tests.
"""
import pytest
from pluggy import HookspecMarker, HookimplMarker
from pluggy.hooks import HookImpl
from pluggy.callers import _multicall


hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


@hookimpl
def hook(arg1, arg2, arg3):
    return arg1, arg2, arg3


@hookimpl(hookwrapper=True)
def wrapper(arg1, arg2, arg3):
    yield


@pytest.fixture(params=[10, 100], ids="hooks={}".format)
def hooks(request):
    return [hook for i in range(request.param)]


@pytest.fixture(params=[10, 100], ids="wrappers={}".format)
def wrappers(request):
    return [wrapper for i in range(request.param)]


def test_hook_and_wrappers_speed(benchmark, hooks, wrappers):
    def setup():
        hook_name = "foo"
        hook_impls = []
        for method in hooks + wrappers:
            f = HookImpl(None, "<temp>", method, method.example_impl)
            hook_impls.append(f)
        caller_kwargs = {"arg1": 1, "arg2": 2, "arg3": 3}
        firstresult = False
        return (hook_name, hook_impls, caller_kwargs, firstresult), {}

    benchmark.pedantic(_multicall, setup=setup)
