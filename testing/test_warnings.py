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
            raise ZeroDivisionError

    class Plugin3:
        @hookimpl(hookwrapper=True)
        def my_hook(self):
            yield

    pm.register(Plugin1(), "plugin1")
    pm.register(Plugin2(), "plugin2")
    pm.register(Plugin3(), "plugin3")
    with (
        pytest.warns(
            PluggyTeardownRaisedWarning,
            match=r"\bplugin2\b.*\bmy_hook\b.*\n.*ZeroDivisionError",
        ) as wc,
        pytest.raises(ZeroDivisionError),
    ):
        pm.hook.my_hook()
    assert len(wc.list) == 1
    assert Path(wc.list[0].filename).name == "test_warnings.py"


def test_hookspec_missing_self_warns(pm: PluginManager) -> None:
    """A hookspec defined as a method without ``self`` emits a DeprecationWarning."""

    class Api:
        @hookspec
        def my_hook(item, extra):
            pass

    with pytest.warns(
        DeprecationWarning,
        match=r"is a method but its first parameter 'item' is not 'self'",
    ):
        pm.add_hookspecs(Api)


def test_hookspec_with_self_no_warning(pm: PluginManager) -> None:
    """A hookspec with ``self`` does not emit a DeprecationWarning."""

    class Api:
        @hookspec
        def my_hook(self, item, extra):
            pass

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        pm.add_hookspecs(Api)


def test_hookspec_staticmethod_no_warning(pm: PluginManager) -> None:
    """A hookspec using @staticmethod does not emit a DeprecationWarning."""

    class Api:
        @staticmethod
        @hookspec
        def my_hook(item, extra) -> None:
            pass

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        pm.add_hookspecs(Api)


def test_hookspec_keyword_only_warns(pm: PluginManager) -> None:
    """Keyword-only hookspec parameters are ignored, so they are deprecated.

    See https://github.com/pytest-dev/pluggy/issues/742.
    """

    class Api:
        @hookspec
        def my_hook(self, arg, *, required_kwonly, defaulted_kwonly=1) -> None:
            pass

    with pytest.warns(
        DeprecationWarning,
        match=r"hookspec 'my_hook' declares keyword-only parameter\(s\) "
        r"'required_kwonly', 'defaulted_kwonly'",
    ) as wc:
        pm.add_hookspecs(Api)
    assert len(wc.list) == 1
    # The warning points at the code which defined the hookspec.
    assert Path(wc.list[0].filename).name == "test_warnings.py"

    # They are not part of the specification's parameters.
    spec = pm.hook.my_hook.spec
    assert spec is not None
    assert spec.argnames == ("arg",)
    assert spec.kwargnames == ()
    assert spec.kwonlyargnames == ("required_kwonly", "defaulted_kwonly")


def test_hookspec_without_keyword_only_no_warning(pm: PluginManager) -> None:
    """A hookspec without keyword-only parameters does not warn."""

    class Api:
        @hookspec
        def my_hook(self, arg, other=1) -> None:
            pass

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        pm.add_hookspecs(Api)
    spec = pm.hook.my_hook.spec
    assert spec is not None
    assert spec.kwonlyargnames == ()


def test_hookimpl_keyword_only_warns(pm: PluginManager) -> None:
    """A hookimpl requesting a keyword-only parameter is deprecated.

    pluggy never passes such a parameter, so an implementation of this hook
    which requests one gets its default (or fails) instead of the call value.
    """

    class Api:
        @hookspec
        def my_hook(self, arg, *, kwonly=1) -> None:
            pass

    with pytest.warns(DeprecationWarning, match=r"hookspec 'my_hook'"):
        pm.add_hookspecs(Api)

    class Plugin:
        @hookimpl
        def my_hook(self, arg, *, kwonly=1):
            return (arg, kwonly)

    with pytest.warns(
        DeprecationWarning,
        match=r"my_hook\(arg, \*, kwonly=1\) declares keyword-only "
        r"parameter\(s\) 'kwonly'",
    ) as wc:
        pm.register(Plugin(), "plugin")
    assert len(wc.list) == 1
    assert Path(wc.list[0].filename).name == "test_warnings.py"

    # Document the behaviour which motivates the warning: the value passed by
    # the caller is dropped and the implementation sees its own default.
    assert pm.hook.my_hook(arg=1, kwonly=2) == [(1, 1)]


def test_hookimpl_without_keyword_only_no_warning(pm: PluginManager) -> None:
    """A hookimpl without keyword-only parameters does not warn."""

    class Api:
        @hookspec
        def my_hook(self, arg, kwonly=1) -> None:
            pass

    pm.add_hookspecs(Api)

    class Plugin:
        @hookimpl
        def my_hook(self, arg, kwonly=1):
            return (arg, kwonly)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        pm.register(Plugin(), "plugin")
    assert pm.hook.my_hook(arg=1, kwonly=2) == [(1, 2)]


def test_hookimpl_keyword_only_warns_even_if_spec_has_none(
    pm: PluginManager,
) -> None:
    """An unrequestable hookimpl parameter is still worth warning about."""

    class Api:
        @hookspec
        def my_hook(self, arg) -> None:
            pass

    pm.add_hookspecs(Api)

    class Plugin:
        @hookimpl
        def my_hook(self, arg, *, kwonly=1):
            return (arg, kwonly)

    with pytest.warns(DeprecationWarning, match=r"declares keyword-only"):
        pm.register(Plugin(), "plugin")
    assert pm.hook.my_hook(arg=1) == [(1, 1)]
