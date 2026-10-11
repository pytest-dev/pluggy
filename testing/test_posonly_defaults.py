from collections.abc import Callable
from functools import wraps

import pytest

from pluggy import HookimplMarker
from pluggy import HookspecMarker
from pluggy import PluginManager


hookspec = HookspecMarker("posonly")
hookimpl = HookimplMarker("posonly")


@pytest.mark.parametrize("style", ["plain", "wrapper", "hookwrapper"])
@pytest.mark.parametrize("supplied", [False, True])
def test_defaulted_positional_only_delivery(style, supplied):
    class Spec:
        @hookspec
        def hello(self, value):
            pass

    class Plain:
        @hookimpl
        def hello(self, value="fallback", /):
            return value

    class Wrapper:
        @hookimpl(wrapper=True)
        def hello(self, value="fallback", /):
            yield
            return value

    class Hookwrapper:
        @hookimpl(hookwrapper=True)
        def hello(self, value="fallback", /):
            outcome = yield
            outcome.force_result(value)

    manager = PluginManager("posonly")
    manager.add_hookspecs(Spec)
    manager.register(
        {"plain": Plain, "wrapper": Wrapper, "hookwrapper": Hookwrapper}[style]()
    )
    if supplied:
        result = manager.hook.hello(value="caller")
        assert result == (["caller"] if style == "plain" else "caller")
    else:
        with pytest.warns(UserWarning):
            result = manager.hook.hello()
        assert result == (["fallback"] if style == "plain" else "fallback")


@pytest.mark.parametrize("kind", ["method", "callable", "decorated"])
@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({}, (1, 2, 3)),
        ({"first": 10}, (10, 2, 3)),
        ({"second": 20}, (1, 20, 3)),
        ({"tail": 30}, (1, 2, 30)),
        ({"first": None, "second": 0, "tail": False}, (None, 0, False)),
    ],
)
def test_positional_only_default_gaps(kind, kwargs, expected):
    positional_calls = []

    class Spec:
        @hookspec
        def hello(self):
            pass

    def decorate(function: Callable[..., object]) -> Callable[..., object]:
        @wraps(function)
        def wrapped(*args, **kwargs):
            positional_calls.append(args)
            return function(*args, **kwargs)

        return wrapped

    class Plugin:
        @hookimpl
        def hello(self, first=1, second=2, /, tail=3):
            return first, second, tail

    class CallablePlugin:
        def __call__(self, first=1, second=2, /, tail=3):
            return first, second, tail

    manager = PluginManager("posonly")
    manager.add_hookspecs(Spec)
    if kind == "method":
        manager.register(Plugin())
        result = manager.hook.hello(**kwargs)
    else:
        function = CallablePlugin() if kind == "callable" else decorate(Plugin().hello)
        result = manager.hook.hello.call_extra([function], kwargs)
    assert result == [expected]
    if kind == "decorated":
        if "second" in kwargs:
            assert positional_calls == [expected[:2]]
        elif "first" in kwargs:
            assert positional_calls == [expected[:1]]
        else:
            assert positional_calls == [()]


def test_required_positional_only_control():
    class Spec:
        @hookspec
        def hello(self, first, second=20):
            pass

    class Plugin:
        @hookimpl
        def hello(self, first, second=2, /, tail=3):
            return first, second, tail

    manager = PluginManager("posonly")
    manager.add_hookspecs(Spec)
    manager.register(Plugin())
    assert manager.hook.hello(first=10) == [(10, 20, 3)]
