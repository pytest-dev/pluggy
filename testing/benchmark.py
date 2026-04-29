"""
Benchmarking and performance tests.
"""

import inspect
import sys
from typing import Any

import pytest

from pluggy import HookimplMarker
from pluggy import HookspecMarker
from pluggy import PluginManager
from pluggy._callers import _multicall
from pluggy._hooks import HookImpl
from pluggy._hooks import varnames


_PYPY = hasattr(sys, "pypy_version_info")


def _varnames_legacy(func: object) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Pre-PEP 649 implementation using inspect.signature for comparison."""
    if inspect.isclass(func):
        try:
            func = func.__init__
        except AttributeError:
            return (), ()
    elif not inspect.isroutine(func):
        try:
            func = getattr(func, "__call__", func)
        except Exception:
            return (), ()

    try:
        sig = inspect.signature(
            func.__func__ if inspect.ismethod(func) else func  # type: ignore[arg-type]
        )
    except TypeError:
        return (), ()

    _valid_param_kinds = (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )
    _valid_params = {
        name: param
        for name, param in sig.parameters.items()
        if param.kind in _valid_param_kinds
    }
    args = tuple(_valid_params)
    defaults = (
        tuple(
            param.default
            for param in _valid_params.values()
            if param.default is not param.empty
        )
        or None
    )

    if defaults:
        index = -len(defaults)
        args, kwargs = args[:index], tuple(args[index:])
    else:
        kwargs = ()

    if not _PYPY:
        implicit_names: tuple[str, ...] = ("self",)
    else:
        implicit_names = ("self", "obj")
    if args:
        qualname: str = getattr(func, "__qualname__", "")
        if inspect.ismethod(func) or ("." in qualname and args[0] in implicit_names):
            args = args[1:]

    return args, kwargs


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
        hook_impls = []
        for method in hooks + wrappers:
            f = HookImpl(None, "<temp>", method, method.example_impl)
            hook_impls.append(f)
        caller_kwargs = {"arg1": 1, "arg2": 2, "arg3": 3}
        firstresult = False
        return (hook_name, hook_impls, caller_kwargs, firstresult), {}

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


def _plain_func(x: int, y: str, z: float = 1.0) -> None:
    pass


class _MethodHolder:
    def method(self, x: int, y: str, z: float = 1.0) -> None:
        pass


_varnames_funcs = [
    pytest.param(_plain_func, id="plain_function"),
    pytest.param(_MethodHolder.method, id="unbound_method"),
    pytest.param(_MethodHolder().method, id="bound_method"),
    pytest.param(_MethodHolder, id="class"),
]


@pytest.mark.parametrize("func", _varnames_funcs)
def test_varnames(benchmark, func: object) -> None:
    benchmark(varnames, func)


@pytest.mark.parametrize("func", _varnames_funcs)
def test_varnames_legacy(benchmark, func: object) -> None:
    benchmark(_varnames_legacy, func)
