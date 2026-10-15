from functools import wraps
import types
from typing import Any

import pytest

from pluggy import HookimplMarker
from pluggy import HookspecMarker
from pluggy import PluginManager


hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


@pytest.mark.parametrize("namespace_kind", ["module", "class", "instance"])
@pytest.mark.parametrize(
    "constructor", ["implicit", "required", "default", "inherited", "wrapped"]
)
def test_class_valued_hookspec(namespace_kind: str, constructor: str) -> None:
    class Implicit:
        pass

    class Required:
        def __init__(self, value: object) -> None:
            raise AssertionError("hookspec constructors must not execute")

    class Default:
        def __init__(self, value: object = "fallback") -> None:
            raise AssertionError("hookspec constructors must not execute")

    class Inherited(Default):
        pass

    class Wrapped:
        @wraps(Default.__init__)  # type: ignore[misc]
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise AssertionError("hookspec constructors must not execute")

    specification = hookspec(
        {
            "implicit": Implicit,
            "required": Required,
            "default": Default,
            "inherited": Inherited,
            "wrapped": Wrapped,
        }[constructor]
    )
    namespace: Any
    if namespace_kind == "module":
        namespace = types.ModuleType("specification")
        setattr(namespace, "hook", specification)
    else:
        namespace_class = type("Specification", (), {"hook": specification})
        namespace = namespace_class if namespace_kind == "class" else namespace_class()
    pm = PluginManager("example")
    pm.add_hookspecs(namespace)
    spec = pm.hook.hook.spec
    assert spec is not None
    assert spec.function is specification
    assert spec.argnames == (("value",) if constructor == "required" else ())
    assert spec.kwargnames == (
        () if constructor in ("implicit", "required") else ("value",)
    )
    assert spec.kwargdefaults == (
        {} if constructor in ("implicit", "required") else {"value": "fallback"}
    )

    plugin = types.ModuleType("implementation")
    if constructor == "implicit":
        @hookimpl
        def empty_hook() -> str:
            return "control"

        setattr(plugin, "hook", empty_hook)
        pm.register(plugin)
        assert pm.hook.hook() == ["control"]
    else:
        @hookimpl
        def value_hook(value: object) -> object:
            return value

        setattr(plugin, "hook", value_hook)
        pm.register(plugin)
        assert pm.hook.hook(value="caller") == ["caller"]
        if constructor != "required":
            assert pm.hook.hook() == ["fallback"]


def test_class_valued_hookimpl_is_still_ignored() -> None:
    plugin = types.ModuleType("implementation")

    @hookimpl
    class Implementation:
        pass

    setattr(plugin, "hook", Implementation)
    pm = PluginManager("example")
    assert pm.parse_hookimpl_opts(plugin, "hook") is None
    pm.register(plugin)
    assert pm.get_hookcallers(plugin) == []
