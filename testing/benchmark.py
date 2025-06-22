"""
Benchmarking and performance tests.
"""

from typing import Any

import pytest

from pluggy import PluginManager
from pluggy import ProjectSpec
from pluggy._callers import _multicall
from pluggy._hook_impl import WrapperImpl


project_spec = ProjectSpec("example")
hookspec = project_spec.hookspec
hookimpl = project_spec.hookimpl


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
        normal_impls = []
        wrapper_impls = []

        for method in hooks + wrappers:
            config = project_spec.get_hookimpl_config(method)
            assert config is not None  # Benchmark functions should be decorated
            f = config.create_hookimpl(
                None,
                "<temp>",
                method,
            )
            # Separate normal and wrapper implementations
            if isinstance(f, WrapperImpl):
                wrapper_impls.append(f)
            else:
                normal_impls.append(f)

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
