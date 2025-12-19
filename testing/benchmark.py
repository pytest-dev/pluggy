"""
Benchmarking and performance tests.
"""

from typing import Any

import pytest

from pluggy import HookimplMarker
from pluggy import HookspecMarker
from pluggy import PluginManager
from pluggy._callers import _multicall
from pluggy._hooks import _create_hook_implementation
from pluggy._hooks import _NormalHookImplementation
from pluggy._hooks import _WrapperHookImplementation


hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


@hookimpl
def hook(arg1, arg2, arg3):
    return arg1, arg2, arg3


@hookimpl(wrapper=True)
def wrapper(arg1, arg2, arg3):
    return (yield)


@pytest.fixture(params=[10, 100], ids="hooks={}".format)
def hooks(request: Any) -> list[object]:
    return [hook for i in range(request.param)]


@pytest.fixture(params=[10, 100], ids="wrappers={}".format)
def wrappers(request: Any) -> list[object]:
    return [wrapper for i in range(request.param)]


def test_hook_and_wrappers_speed(benchmark, hooks, wrappers) -> None:
    def setup():
        hook_name = "foo"
        normal_impls: list[_NormalHookImplementation] = []
        wrapper_impls: list[_WrapperHookImplementation] = []
        for method in hooks:
            opts = method.example_impl
            f = _create_hook_implementation(None, "<temp>", method, opts)
            normal_impls.append(f)  # type: ignore[arg-type]
        for method in wrappers:
            opts = method.example_impl
            f = _create_hook_implementation(None, "<temp>", method, opts)
            wrapper_impls.append(f)  # type: ignore[arg-type]
        caller_kwargs = {"arg1": 1, "arg2": 2, "arg3": 3}
        firstresult = False
        return (hook_name, normal_impls, wrapper_impls, caller_kwargs, firstresult), {}

    benchmark.pedantic(_multicall, setup=setup, rounds=10)


@pytest.mark.parametrize(
    ("plugins, wrappers, nesting"),
    [
        (1, 1, 0),
        (1, 1, 1),
        (1, 1, 5),
        (1, 5, 1),
        (1, 5, 5),
        (5, 1, 1),
        (5, 1, 5),
        (5, 5, 1),
        (5, 5, 5),
        (20, 20, 0),
        (100, 100, 0),
    ],
)
def test_call_hook(benchmark, plugins, wrappers, nesting) -> None:
    pm = PluginManager("example")

    class HookSpec:
        @hookspec
        def fun(self, hooks, nesting: int):
            pass

    class Plugin:
        def __init__(self, num: int) -> None:
            self.num = num

        def __repr__(self) -> str:
            return f"<Plugin {self.num}>"

        @hookimpl
        def fun(self, hooks, nesting: int) -> None:
            if nesting:
                hooks.fun(hooks=hooks, nesting=nesting - 1)

    class PluginWrap:
        def __init__(self, num: int) -> None:
            self.num = num

        def __repr__(self) -> str:
            return f"<PluginWrap {self.num}>"

        @hookimpl(wrapper=True)
        def fun(self):
            return (yield)

    pm.add_hookspecs(HookSpec)

    for i in range(plugins):
        pm.register(Plugin(i), name=f"plug_{i}")
    for i in range(wrappers):
        pm.register(PluginWrap(i), name=f"wrap_plug_{i}")

    benchmark(pm.hook.fun, hooks=pm.hook, nesting=nesting)
