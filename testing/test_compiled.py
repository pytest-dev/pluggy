"""
Hook discovery on compiled functions (Cython).

The Cython tests are skipped unless Cython and setuptools are installed (they
also need a C compiler). The ``cython`` tox factor installs both and sets
``PLUGGY_REQUIRE_CYTHON`` so that a missing dependency fails instead of
skipping; CI runs it as a dedicated job.
"""

from collections.abc import Iterator
import functools
import importlib
import importlib.util
import os
import sys
import textwrap
import types

import pytest

from pluggy import PluginManager
from pluggy._manager import _is_function_like


CYTHON_SOURCE = textwrap.dedent(
    """
    # cython: language_level=3
    import pluggy

    hookspec = pluggy.HookspecMarker("example")
    hookimpl = pluggy.HookimplMarker("example")


    class Spec:
        @hookspec
        def hello(self, arg):
            pass


    @hookimpl
    def hello(arg):
        return ("module", arg)


    class Plugin:
        @hookimpl
        def hello(self, arg):
            return ("method", arg)


    class StaticPlugin:
        @staticmethod
        @hookimpl
        def hello(arg):
            return ("static", arg)


    class ClassPlugin:
        @classmethod
        @hookimpl
        def hello(cls, arg):
            return ("class", cls.__name__, arg)


    cdef class ExtPlugin:
        @hookimpl
        def hello(self, arg):
            return ("ext", arg)
    """
)


@pytest.fixture(scope="module")
def cymod(tmp_path_factory: pytest.TempPathFactory) -> Iterator[types.ModuleType]:
    missing = [
        m for m in ("Cython", "setuptools") if importlib.util.find_spec(m) is None
    ]
    if missing and not os.environ.get("PLUGGY_REQUIRE_CYTHON"):
        pytest.skip(f"needs {', '.join(missing)}")
    import pyximport

    src = tmp_path_factory.mktemp("cysrc")
    (src / "pluggy_cy_hooks.pyx").write_text(CYTHON_SOURCE)
    importers = pyximport.install(
        build_dir=str(tmp_path_factory.mktemp("cybuild")), language_level=3
    )
    sys.path.insert(0, str(src))
    try:
        yield importlib.import_module("pluggy_cy_hooks")
    finally:
        sys.path.remove(str(src))
        sys.modules.pop("pluggy_cy_hooks", None)
        pyximport.uninstall(*importers)


@pytest.fixture
def cy_pm(cymod: types.ModuleType) -> PluginManager:
    pm = PluginManager("example")
    pm.add_hookspecs(cymod.Spec)
    return pm


def test_cython_function_is_compiled(cymod: types.ModuleType) -> None:
    """Guard: if Cython ever emits real functions, the tests below prove nothing."""
    assert not isinstance(cymod.hello, types.FunctionType)
    assert _is_function_like(cymod.hello)


def test_cython_hookspec(cy_pm: PluginManager) -> None:
    assert cy_pm.hook.hello.has_spec()


@pytest.mark.parametrize(
    "plugin_name, expected",
    [
        pytest.param(None, ("module", 1), id="module"),
        pytest.param("Plugin", ("method", 1), id="method"),
        pytest.param("StaticPlugin", ("static", 1), id="staticmethod"),
        pytest.param("ClassPlugin", ("class", "ClassPlugin", 1), id="classmethod"),
        pytest.param("ExtPlugin", ("ext", 1), id="cdef-class-method"),
    ],
)
def test_cython_hookimpl(
    cymod: types.ModuleType,
    cy_pm: PluginManager,
    plugin_name: str | None,
    expected: tuple[object, ...],
) -> None:
    plugin = cymod if plugin_name is None else getattr(cymod, plugin_name)()
    cy_pm.register(plugin)
    assert cy_pm.hook.hello(arg=1) == [expected]


def test_cython_hookimpl_on_class(
    cymod: types.ModuleType, cy_pm: PluginManager
) -> None:
    """Registering the class itself leaves methods unbound, as for Python."""
    cy_pm.register(cymod.ClassPlugin)
    assert cy_pm.hook.hello(arg=1) == [("class", "ClassPlugin", 1)]


@pytest.mark.parametrize(
    "obj",
    [
        pytest.param(functools.cached_property(lambda self: 1), id="cached_property"),
        pytest.param(property(lambda self: 1), id="property"),
        pytest.param(42, id="int"),
    ],
)
def test_is_function_like_rejects(obj: object) -> None:
    """Python-level descriptors must not be treated as functions (or evaluated)."""
    assert not _is_function_like(obj)
