"""Regression tests for issue #815."""

from __future__ import annotations

from collections.abc import Callable

from pluggy import HookimplMarker
from pluggy import HookspecMarker
from pluggy import PluginManager


def make_manager() -> PluginManager:
    hookspec = HookspecMarker("monitor-undo")
    hookimpl = HookimplMarker("monitor-undo")

    class Spec:
        @hookspec
        def ping(self):
            """Test hook."""

    class Plugin:
        @hookimpl
        def ping(self):
            return "ok"

    manager = PluginManager("monitor-undo")
    manager.add_hookspecs(Spec)
    manager.register(Plugin())
    return manager


def add_monitor(
    manager: PluginManager, events: list[str], label: str
) -> Callable[[], None]:
    def before(*args):
        events.append(f"{label}:before")

    def after(*args):
        events.append(f"{label}:after")

    return manager.add_hookcall_monitoring(before, after)


def test_non_lifo_removal():
    manager = make_manager()
    events: list[str] = []

    undo_a = add_monitor(manager, events, "A")
    undo_b = add_monitor(manager, events, "B")

    undo_a()

    assert manager.hook.ping() == ["ok"]
    assert events == ["B:before", "B:after"]

    events.clear()
    undo_b()

    assert manager.hook.ping() == ["ok"]
    assert events == []


def test_repeated_undo():
    manager = make_manager()
    events: list[str] = []

    undo_a = add_monitor(manager, events, "A")
    undo_a()

    undo_b = add_monitor(manager, events, "B")
    undo_a()

    assert manager.hook.ping() == ["ok"]
    assert events == ["B:before", "B:after"]

    undo_b()


def test_lifo_order():
    manager = make_manager()
    events: list[str] = []

    undo_a = add_monitor(manager, events, "A")
    undo_b = add_monitor(manager, events, "B")

    assert manager.hook.ping() == ["ok"]
    assert events == [
        "B:before",
        "A:before",
        "A:after",
        "B:after",
    ]

    events.clear()
    undo_b()

    assert manager.hook.ping() == ["ok"]
    assert events == ["A:before", "A:after"]

    undo_a()


def test_undo_during_hook():
    manager = make_manager()
    events: list[str] = []
    undo_callbacks: list[Callable[[], None]] = []

    def before(*args):
        events.append("before")
        undo_callbacks[0]()

    def after(*args):
        events.append("after")

    undo_callbacks.append(manager.add_hookcall_monitoring(before, after))

    assert manager.hook.ping() == ["ok"]
    assert events == ["before", "after"]

    events.clear()
    assert manager.hook.ping() == ["ok"]
    assert events == []


def test_restore_custom_executor():
    manager = make_manager()
    original = manager._inner_hookexec

    def custom_exec(name, impls, kwargs, firstresult):
        return original(name, impls, kwargs, firstresult)

    manager._inner_hookexec = custom_exec
    events: list[str] = []

    undo = add_monitor(manager, events, "A")
    undo()

    assert manager._inner_hookexec is custom_exec
    assert manager.hook.ping() == ["ok"]
    assert events == []


def test_enable_tracing_removed_before_monitor() -> None:
    manager = make_manager()
    messages: list[str] = []
    events: list[str] = []

    manager.trace.root.setwriter(messages.append)

    undo_trace = manager.enable_tracing()
    undo_monitor = add_monitor(manager, events, "B")

    undo_trace()

    assert manager.hook.ping() == ["ok"]
    assert events == ["B:before", "B:after"]
    assert messages == []
    assert manager.trace.root.indent == 0

    undo_monitor()
    undo_trace()

    events.clear()
    assert manager.hook.ping() == ["ok"]
    assert events == []


def test_remove_monitor_before_tracing() -> None:
    manager = make_manager()
    messages: list[str] = []
    events: list[str] = []

    manager.trace.root.setwriter(messages.append)

    undo_monitor = add_monitor(manager, events, "A")
    undo_trace = manager.enable_tracing()

    undo_monitor()

    assert manager.hook.ping() == ["ok"]
    assert events == []
    assert messages
    assert manager.trace.root.indent == 0

    messages.clear()
    undo_trace()

    assert manager.hook.ping() == ["ok"]
    assert messages == []
