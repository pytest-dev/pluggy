"""Failed specification validation must leave registered hook callers usable."""

import warnings

import pytest

from pluggy import HookimplMarker
from pluggy import HookspecMarker
from pluggy import PluginManager
from pluggy import PluginValidationError


hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


@pytest.mark.parametrize("historic", [False, True])
def test_failed_hookspec_can_be_retried(pm: PluginManager, historic: bool) -> None:
    class Hooks:
        @hookspec(historic=historic)
        def process(self, value: int) -> int:
            raise NotImplementedError  # pragma: no cover

    class ValidPlugin:
        @hookimpl
        def process(self, value: int) -> int:
            return value + 1

    class InvalidPlugin:
        @hookimpl
        def process(self, unexpected: int) -> int:
            return unexpected

    valid, invalid = ValidPlugin(), InvalidPlugin()
    pm.register(valid)
    pm.register(invalid)
    caller = pm.hook.process
    impls = caller.get_hookimpls()
    subset = pm.subset_hook_caller("process", remove_plugins=[invalid])

    with pytest.raises(PluginValidationError, match="unexpected") as excinfo:
        pm.add_hookspecs(Hooks)

    assert excinfo.value.plugin is invalid
    assert pm.hook.process is caller
    assert not caller.has_spec()
    assert not caller.is_historic()
    assert caller.get_hookimpls() == impls
    assert pm.get_plugins() == {valid, invalid}

    pm.unregister(invalid)
    pm.add_hookspecs(Hooks)
    assert pm.hook.process is caller
    assert caller.spec is not None
    assert caller.spec.namespace is Hooks
    assert caller.is_historic() is historic
    if historic:
        results: list[int] = []
        subset.call_historic(results.append, {"value": 3})
        pm.register(ValidPlugin())
        assert results == [4, 4]
    else:
        assert caller(value=3) == [4]
        assert subset(value=3) == [4]


def test_failed_hookspec_namespace_installs_nothing(pm: PluginManager) -> None:
    class Hooks:
        @hookspec
        def a_new(self) -> None: ...

        @hookspec
        def b_valid(self, value: int) -> int:
            raise NotImplementedError  # pragma: no cover

        @hookspec
        def z_invalid(self, value: int) -> int:
            raise NotImplementedError  # pragma: no cover

    class ValidPlugin:
        @hookimpl
        def b_valid(self, value: int) -> int:
            return value

    class InvalidPlugin:
        @hookimpl
        def z_invalid(self, unexpected: int) -> int:
            return unexpected

    valid, invalid = ValidPlugin(), InvalidPlugin()
    pm.register(valid)
    pm.register(invalid)
    valid_caller, invalid_caller = pm.hook.b_valid, pm.hook.z_invalid

    with pytest.raises(PluginValidationError, match="unexpected"):
        pm.add_hookspecs(Hooks)

    assert not hasattr(pm.hook, "a_new")
    assert not valid_caller.has_spec()
    assert not invalid_caller.has_spec()
    pm.unregister(invalid)
    pm.add_hookspecs(Hooks)
    assert pm.hook.b_valid is valid_caller
    assert pm.hook.z_invalid is invalid_caller
    assert valid_caller(value=7) == [7]
    assert pm.hook.a_new() == []


@pytest.mark.parametrize("historic", [False, True])
def test_duplicate_hookspec_preserves_existing_state(
    pm: PluginManager, historic: bool
) -> None:
    class ExistingHooks:
        @hookspec(historic=historic)
        def z_existing(self, value: int) -> int:
            raise NotImplementedError  # pragma: no cover

    class MoreHooks:
        @hookspec
        def a_new(self) -> None: ...

        @hookspec
        def z_existing(self, value: int) -> int:
            raise NotImplementedError  # pragma: no cover

    pm.add_hookspecs(ExistingHooks)
    caller = pm.hook.z_existing
    original_spec = caller.spec
    results: list[int] = []
    if historic:
        caller.call_historic(results.append, {"value": 8})

    with pytest.raises(ValueError, match="Hook 'z_existing' is already registered"):
        pm.add_hookspecs(MoreHooks)

    assert pm.hook.z_existing is caller
    assert caller.spec is original_spec
    assert not hasattr(pm.hook, "a_new")

    class Plugin:
        @hookimpl
        def z_existing(self, value: int) -> int:
            return value

    pm.register(Plugin())
    if historic:
        assert results == [8]
    else:
        assert caller(value=8) == [8]


@pytest.mark.parametrize("warn_on_argument", [False, True])
def test_hookspec_warning_as_error_allows_retry(
    pm: PluginManager, warn_on_argument: bool
) -> None:
    warning = UserWarning("deprecated implementation")

    class Hooks:
        @hookspec(
            warn_on_impl=None if warn_on_argument else warning,
            warn_on_impl_args={"value": warning} if warn_on_argument else None,
        )
        def process(self, value: int) -> int:
            raise NotImplementedError  # pragma: no cover

    class Plugin:
        @hookimpl
        def process(self, value: int) -> int:
            return value

    pm.register(Plugin())
    caller = pm.hook.process
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(UserWarning, match="deprecated implementation"):
            pm.add_hookspecs(Hooks)

    assert not caller.has_spec()
    with pytest.warns(UserWarning, match="deprecated implementation") as recorded:
        pm.add_hookspecs(Hooks)
    assert len(recorded) == 1
    assert pm.hook.process is caller
    assert caller(value=5) == [5]
