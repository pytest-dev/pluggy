"""Historic replay failures must only undo the failed registration."""

import pytest

from pluggy import HookimplMarker
from pluggy import HookspecMarker
from pluggy import PluginManager


hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


@pytest.mark.parametrize("exception_type", [RuntimeError, KeyboardInterrupt])
@pytest.mark.parametrize("fail_in_callback", [False, True])
def test_failed_replay_cleans_up_and_allows_retry(
    pm: PluginManager, exception_type: type[BaseException], fail_in_callback: bool
) -> None:
    class Hooks:
        @hookspec
        def a_existing(self) -> None: ...

        @hookspec(historic=True)
        def c_history(self, value: int) -> None: ...

    class Existing:
        @hookimpl
        def a_existing(self) -> str:
            return "existing"

        @hookimpl
        def c_history(self, value: int) -> tuple[str, int]:
            return "existing", value

    class Empty:
        @hookimpl
        def d_empty(self) -> None: ...

    error = exception_type("replay failed")
    fail = True
    calls: list[int] = []
    results: list[tuple[str, int]] = []

    def callback(result: tuple[str, int]) -> None:
        results.append(result)
        if fail and fail_in_callback and result == ("new", 20):
            raise error

    class Plugin:
        @hookimpl
        def a_existing(self) -> str:
            return "new"

        @hookimpl
        def b_new(self) -> str:
            return "new hook"

        @hookimpl
        def c_history(self, value: int) -> tuple[str, int]:
            calls.append(value)
            if fail and not fail_in_callback and value == 20:
                raise error
            return "new", value

        @hookimpl
        def z_unprocessed(self) -> None: ...

    pm.add_hookspecs(Hooks)
    existing = Existing()
    pm.register(existing, "existing")
    empty = Empty()
    pm.register(empty, "empty")
    pm.unregister(empty)
    callers = dict(pm.hook.__dict__)
    impls = {name: caller.get_hookimpls() for name, caller in callers.items()}
    specs = {name: caller.spec for name, caller in callers.items()}
    history = pm.hook.c_history._call_history
    for value in (10, 20):
        pm.hook.c_history.call_historic(callback, {"value": value})
    plugin = Plugin()

    with pytest.raises(exception_type, match="replay failed") as excinfo:
        pm.register(plugin, "new")

    assert excinfo.value is error
    frame_names = [entry.name for entry in excinfo.traceback]
    assert frame_names[-1] == ("callback" if fail_in_callback else "c_history")
    assert frame_names.count("register") == 1
    assert pm.list_name_plugin() == [("existing", existing)]
    assert pm.get_hookcallers(plugin) is None
    assert pm.hook.__dict__ == callers
    for name, caller in callers.items():
        assert getattr(pm.hook, name) is caller
        assert caller.spec is specs[name]
        assert caller.get_hookimpls() == impls[name]
    assert pm.hook.c_history._call_history is history
    assert history is not None and len(history) == 2
    assert calls == [10, 20]  # External effects of replay are retained.
    assert results == [("existing", 10), ("existing", 20), ("new", 10)] + (
        [("new", 20)] if fail_in_callback else []
    )
    assert pm.hook.a_existing() == ["existing"]

    fail = False
    assert pm.register(plugin, "new") == "new"
    assert calls == [10, 20, 10, 20]
    assert results[-2:] == [("new", 10), ("new", 20)]
    assert pm.hook.a_existing() == ["new", "existing"]
    assert pm.hook.b_new() == ["new hook"]
    assert pm.hook.z_unprocessed() == []
    pm.unregister(plugin)
    assert pm.list_name_plugin() == [("existing", existing)]
    for name, caller in callers.items():
        assert caller.get_hookimpls() == impls[name]


@pytest.mark.parametrize("adopted_by", ["spec", "plugin", "both"])
def test_failed_replay_preserves_adopted_new_caller(
    pm: PluginManager, adopted_by: str
) -> None:
    class Hooks:
        @hookspec(historic=True)
        def configure(self) -> None: ...

    class LateHooks:
        @hookspec
        def a_new(self) -> None: ...

    class Nested:
        @hookimpl
        def a_new(self) -> str:
            return "nested"

    nested = Nested()
    error = RuntimeError("outer replay failed")
    saved = []

    class Plugin:
        @hookimpl
        def a_new(self) -> str:
            return "outer"  # pragma: no cover

        @hookimpl
        def configure(self) -> None:
            caller = pm.hook.a_new
            if adopted_by in ("spec", "both"):
                pm.add_hookspecs(LateHooks)
            if adopted_by in ("plugin", "both"):
                pm.register(nested, "nested")
            saved.append((caller, caller.spec, caller.get_hookimpls()[-1:]))
            raise error

    pm.add_hookspecs(Hooks)
    pm.hook.configure.call_historic()
    with pytest.raises(RuntimeError) as excinfo:
        pm.register(Plugin(), "outer")

    assert excinfo.value is error
    caller, spec, nested_impls = saved[0]
    assert pm.hook.a_new is caller
    assert caller.spec is spec
    assert caller.has_spec() is (adopted_by != "plugin")
    assert pm.hook.configure.get_hookimpls() == []
    if adopted_by == "spec":
        assert pm.list_name_plugin() == []
        assert caller.get_hookimpls() == []
        assert caller() == []
    else:
        assert pm.list_name_plugin() == [("nested", nested)]
        assert caller.get_hookimpls() == nested_impls
        assert caller() == ["nested"]


@pytest.mark.parametrize(
    "replacement", ["other", "same", "same_without_hooks", "blocked", "removed"]
)
def test_failed_replay_preserves_reentrant_registry_changes(
    pm: PluginManager, replacement: str
) -> None:
    class Hooks:
        @hookspec(historic=True)
        def configure(self) -> None: ...

    class Other:
        @hookimpl
        def a_new(self) -> str:
            return "other"

    other = Other()
    error = RuntimeError("replay replaced registration")

    class Plugin:
        replace = True

        @hookimpl
        def a_new(self) -> str:
            return "same"

        @hookimpl
        def configure(self) -> None:
            if self.replace:
                self.replace = False
                pm.unregister(name="plugin")
                if replacement == "other":
                    pm.register(other, "plugin")
                elif replacement == "same":
                    pm.register(self, "plugin")
                elif replacement == "same_without_hooks":
                    self.a_new = None  # type: ignore[assignment]
                    self.configure = None  # type: ignore[assignment]
                    pm.register(self, "plugin")
                elif replacement == "blocked":
                    pm.set_blocked("plugin")
                raise error

    pm.add_hookspecs(Hooks)
    pm.hook.configure.call_historic()
    plugin = Plugin()
    with pytest.raises(RuntimeError) as excinfo:
        pm.register(plugin, "plugin")

    assert excinfo.value is error
    if replacement == "other":
        assert pm.list_name_plugin() == [("plugin", other)]
        assert pm.hook.a_new() == ["other"]
        assert pm.hook.configure.get_hookimpls() == []
    elif replacement == "same":
        assert pm.list_name_plugin() == [("plugin", plugin)]
        assert pm.hook.a_new() == ["same"]
        assert len(pm.hook.configure.get_hookimpls()) == 1
        pm.unregister(plugin)
        assert pm.hook.a_new.get_hookimpls() == []
        assert pm.hook.configure.get_hookimpls() == []
    elif replacement == "same_without_hooks":
        assert pm.list_name_plugin() == [("plugin", plugin)]
        assert pm.get_hookcallers(plugin) == []
        assert not hasattr(pm.hook, "a_new")
        assert pm.hook.configure.get_hookimpls() == []
    else:
        assert pm.get_plugin("plugin") is None
        assert pm.is_blocked("plugin") is (replacement == "blocked")
        assert not hasattr(pm.hook, "a_new")
        assert pm.hook.configure.get_hookimpls() == []


def test_rollback_does_not_call_plugin_equality(pm: PluginManager) -> None:
    class Hooks:
        @hookspec(historic=True)
        def configure(self) -> None: ...

    error = RuntimeError("original replay failure")

    class Plugin:
        fail = False

        def __eq__(self, other: object) -> bool:
            if self.fail:
                raise AssertionError("equality must not mask the replay error")
            return self is other

        @hookimpl
        def a_new(self) -> None: ...

        @hookimpl
        def configure(self) -> None:
            self.fail = True
            raise error

    pm.add_hookspecs(Hooks)
    pm.hook.configure.call_historic()
    with pytest.raises(RuntimeError) as excinfo:
        pm.register(Plugin(), "plugin")

    assert excinfo.value is error
    assert pm.list_name_plugin() == []
    assert not hasattr(pm.hook, "a_new")
    assert pm.hook.configure.get_hookimpls() == []
