from collections.abc import Callable
from functools import wraps
import inspect
import warnings

import pytest

from pluggy import HookimplMarker
from pluggy import HookspecMarker
from pluggy import PluginManager


hookspec = HookspecMarker("posonly")
hookimpl = HookimplMarker("posonly")


@pytest.mark.parametrize("style", ["plain", "wrapper", "hookwrapper"])
@pytest.mark.parametrize("defaulted", [False, True])
def test_positional_only_deprecation_preserves_calls(style, defaulted):
    class Spec:
        @hookspec
        def hello(self, value):
            pass

    def plain_required(self, value, /):
        return value

    def plain_defaulted(self, value="fallback", /):
        return value

    def wrapper_required(self, value, /):
        yield
        return value

    def wrapper_defaulted(self, value="fallback", /):
        yield
        return value

    def hookwrapper_required(self, value, /):
        outcome = yield
        outcome.force_result([value])

    def hookwrapper_defaulted(self, value="fallback", /):
        outcome = yield
        outcome.force_result([value])

    variants: dict[tuple[str, bool], Callable[..., object]] = {
        ("plain", False): plain_required,
        ("plain", True): plain_defaulted,
        ("wrapper", False): wrapper_required,
        ("wrapper", True): wrapper_defaulted,
        ("hookwrapper", False): hookwrapper_required,
        ("hookwrapper", True): hookwrapper_defaulted,
    }
    hello = variants[style, defaulted]
    marked = hookimpl(wrapper=style == "wrapper", hookwrapper=style == "hookwrapper")(
        hello
    )
    plugin = type("Plugin", (), {"hello": marked})()
    manager = PluginManager("posonly")
    manager.add_hookspecs(Spec)
    with pytest.warns(DeprecationWarning, match="Positional-only.*pluggy 2.0") as recorded:
        manager.register(plugin)
    assert len(recorded) == 1
    assert recorded[0].filename == plain_required.__code__.co_filename
    assert recorded[0].lineno == inspect.getsourcelines(hello)[1]
    if defaulted:
        # Preserve the pre-existing failure rather than adding new binding semantics.
        with pytest.raises(TypeError, match="positional-only"):
            manager.hook.hello(value="caller")
        with pytest.warns(UserWarning, match="cannot be found"):
            result = manager.hook.hello()
        assert result == (["fallback"] if style != "wrapper" else "fallback")
    else:
        result = manager.hook.hello(value="caller")
        assert result == (["caller"] if style != "wrapper" else "caller")


@pytest.mark.parametrize(
    "kind", ["method", "classmethod", "staticmethod", "decorated", "callable", "class"]
)
def test_positional_only_callable_shapes(kind):
    class Spec:
        @hookspec
        def hello(self, value):
            pass

    class Plugin:
        @hookimpl
        def hello(self, value, /):
            return value

    class ClassPlugin:
        @classmethod
        @hookimpl
        def hello(cls, value, /):
            return value

    class StaticPlugin:
        @staticmethod
        @hookimpl
        def hello(value, /):
            return value

    class CallablePlugin:
        def __call__(self, value, /):
            return value

    class ExtraClass:
        def __init__(self, value, /):
            self.value = value

    def decorate(function: Callable[..., object]) -> Callable[..., object]:
        @wraps(function)
        def wrapped(*args, **kwargs):
            return function(*args, **kwargs)

        return wrapped

    manager = PluginManager("posonly")
    manager.add_hookspecs(Spec)
    with pytest.warns(DeprecationWarning, match="Positional-only") as recorded:
        if kind in ("method", "classmethod", "staticmethod"):
            plugin = {
                "method": Plugin,
                "classmethod": ClassPlugin,
                "staticmethod": StaticPlugin,
            }[kind]()
            manager.register(plugin)
            result = manager.hook.hello(value="caller")
        else:
            extras: dict[str, Callable[..., object]] = {
                "decorated": decorate(Plugin().hello),
                "callable": CallablePlugin(),
                "class": ExtraClass,
            }
            result = manager.hook.hello.call_extra([extras[kind]], {"value": "caller"})
    assert len(recorded) == 1
    assert "'self'" not in str(recorded[0].message)
    assert "'cls'" not in str(recorded[0].message)
    if kind == "class":
        assert result[0].value == "caller"
    else:
        assert result == ["caller"]


def test_implicit_positional_only_receiver_does_not_warn():
    class Spec:
        @hookspec
        def hello(self, value, /):
            pass

    class Plugin:
        @hookimpl
        def hello(self, /, value="fallback"):
            return value

    manager = PluginManager("posonly")
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        manager.add_hookspecs(Spec)
        manager.register(Plugin())
        assert manager.hook.hello(value="caller") == ["caller"]
    assert not recorded
