from pathlib import Path
import warnings

import pytest

from pluggy import HookimplMarker
from pluggy import HookspecMarker
from pluggy import PluggyTeardownRaisedWarning
from pluggy import PluginManager


hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


def test_teardown_raised_warning(pm: PluginManager) -> None:
    class Api:
        @hookspec
        def my_hook(self):
            raise NotImplementedError()

    pm.add_hookspecs(Api)

    class Plugin1:
        @hookimpl
        def my_hook(self):
            pass

    class Plugin2:
        @hookimpl(hookwrapper=True)
        def my_hook(self):
            yield
            1 / 0

    class Plugin3:
        @hookimpl(hookwrapper=True)
        def my_hook(self):
            yield

    pm.register(Plugin1(), "plugin1")
    pm.register(Plugin2(), "plugin2")
    pm.register(Plugin3(), "plugin3")
    with pytest.warns(
        PluggyTeardownRaisedWarning,
        match=r"\bplugin2\b.*\bmy_hook\b.*\n.*ZeroDivisionError",
    ) as wc:
        with pytest.raises(ZeroDivisionError):
            pm.hook.my_hook()
    assert len(wc.list) == 1
    assert Path(wc.list[0].filename).name == "test_warnings.py"


def test_hookspec_missing_self_warns(pm: PluginManager) -> None:
    """A hookspec defined as a method without ``self`` emits a FutureWarning."""

    class Api:
        @hookspec
        def my_hook(item, extra):
            pass

    with pytest.warns(
        FutureWarning,
        match=r"is a method but its first parameter 'item' is not 'self'",
    ):
        pm.add_hookspecs(Api)


def test_hookspec_with_self_no_warning(pm: PluginManager) -> None:
    """A hookspec with ``self`` does not emit a FutureWarning."""

    class Api:
        @hookspec
        def my_hook(self, item, extra):
            pass

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        pm.add_hookspecs(Api)


def test_hookspec_staticmethod_no_warning(pm: PluginManager) -> None:
    """A hookspec using @staticmethod does not emit a FutureWarning."""

    class Api:
        @staticmethod
        @hookspec
        def my_hook(item, extra) -> None:
            pass

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        pm.add_hookspecs(Api)
