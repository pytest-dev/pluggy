from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence
import gc
from itertools import permutations
from typing import Any
import weakref

import pytest

from pluggy import HookImpl
from pluggy import HookimplMarker
from pluggy import PluginManager
from pluggy import Result


hookimpl = HookimplMarker("example")


class Plugin:
    @hookimpl
    def he_method1(self, arg: int) -> int:
        return arg


def add_monitor(pm: PluginManager, label: str, events: list[str]) -> Callable[[], None]:
    def before(
        name: str, implementations: Sequence[HookImpl], kwargs: Mapping[str, Any]
    ) -> None:
        events.append(f"{label}:before")

    def after(
        outcome: Result[Any],
        name: str,
        implementations: Sequence[HookImpl],
        kwargs: Mapping[str, Any],
    ) -> None:
        events.append(f"{label}:after")

    return pm.add_hookcall_monitoring(before, after)


@pytest.mark.parametrize("order", list(permutations(("A", "B", "C"))))
def test_monitor_undo_order(he_pm: PluginManager, order: tuple[str, ...]) -> None:
    he_pm.register(Plugin())
    events: list[str] = []
    labels = ["A", "B", "C"]
    undos = {label: add_monitor(he_pm, label, events) for label in labels}

    def call() -> None:
        events.clear()
        assert he_pm.hook.he_method1(arg=42) == [42]
        assert events == [f"{label}:before" for label in reversed(labels)] + [
            f"{label}:after" for label in labels
        ]

    call()
    for label in order:
        undos[label]()
        labels.remove(label)
        call()
        undos[label]()
        call()


def test_monitor_undo_does_not_remove_new_monitor(he_pm: PluginManager) -> None:
    he_pm.register(Plugin())
    events: list[str] = []
    old_undo = add_monitor(he_pm, "old", events)
    old_undo()
    undo = add_monitor(he_pm, "new", events)
    old_undo()
    assert he_pm.hook.he_method1(arg=42) == [42]
    assert events == ["new:before", "new:after"]
    undo()


@pytest.mark.parametrize("remove_before", [False, True])
@pytest.mark.parametrize("remove_self", [False, True])
def test_monitor_undo_during_call(
    he_pm: PluginManager, remove_before: bool, remove_self: bool
) -> None:
    he_pm.register(Plugin())
    events: list[str] = []
    undo_old = add_monitor(he_pm, "old", events)

    def before(
        name: str, implementations: Sequence[HookImpl], kwargs: Mapping[str, Any]
    ) -> None:
        events.append("new:before")
        if remove_before:
            (undo_new if remove_self else undo_old)()

    def after(
        outcome: Result[Any],
        name: str,
        implementations: Sequence[HookImpl],
        kwargs: Mapping[str, Any],
    ) -> None:
        events.append("new:after")
        if not remove_before:
            (undo_new if remove_self else undo_old)()

    undo_new = he_pm.add_hookcall_monitoring(before, after)
    assert he_pm.hook.he_method1(arg=42) == [42]
    assert events == ["new:before", "old:before", "old:after", "new:after"]
    events.clear()
    assert he_pm.hook.he_method1(arg=42) == [42]
    label = "old" if remove_self else "new"
    assert events == [f"{label}:before", f"{label}:after"]
    undo_old()
    undo_new()


def test_removing_deep_monitor_preserves_in_flight_call(he_pm: PluginManager) -> None:
    he_pm.register(Plugin())
    events: list[str] = []
    undo_oldest = add_monitor(he_pm, "oldest", events)
    undo_middle = add_monitor(he_pm, "middle", events)

    def before(
        name: str, implementations: Sequence[HookImpl], kwargs: Mapping[str, Any]
    ) -> None:
        events.append("newest:before")
        undo_oldest()

    def after(
        outcome: Result[Any],
        name: str,
        implementations: Sequence[HookImpl],
        kwargs: Mapping[str, Any],
    ) -> None:
        events.append("newest:after")

    undo_newest = he_pm.add_hookcall_monitoring(before, after)
    assert he_pm.hook.he_method1(arg=42) == [42]
    assert events == [
        "newest:before",
        "middle:before",
        "oldest:before",
        "oldest:after",
        "middle:after",
        "newest:after",
    ]
    events.clear()
    assert he_pm.hook.he_method1(arg=42) == [42]
    assert events == ["newest:before", "middle:before", "middle:after", "newest:after"]
    undo_middle()
    undo_newest()


@pytest.mark.parametrize("tracing_first", [False, True])
def test_monitor_undo_keeps_other_tracing(
    he_pm: PluginManager, tracing_first: bool
) -> None:
    he_pm.register(Plugin())
    events: list[str] = []
    traces: list[str] = []
    he_pm.trace.root.setwriter(traces.append)
    if tracing_first:
        undo_first = he_pm.enable_tracing()
        undo_second = add_monitor(he_pm, "monitor", events)
    else:
        undo_first = add_monitor(he_pm, "monitor", events)
        undo_second = he_pm.enable_tracing()
    undo_first()
    assert he_pm.hook.he_method1(arg=42) == [42]
    assert events == (["monitor:before", "monitor:after"] if tracing_first else [])
    assert len(traces) == (0 if tracing_first else 2)
    assert he_pm.trace.root.indent == 0
    undo_second()
    events.clear()
    traces.clear()
    assert he_pm.hook.he_method1(arg=42) == [42]
    assert events == traces == []


@pytest.mark.parametrize("raises", [False, True])
def test_monitor_undo_preserves_outcomes(he_pm: PluginManager, raises: bool) -> None:
    error = ValueError("from hook")

    class OutcomePlugin:
        @hookimpl
        def he_method1(self, arg: int) -> int:
            if raises:
                raise error
            return arg

    he_pm.register(OutcomePlugin())
    observed: list[object] = []

    def replace_result(
        outcome: Result[Any],
        name: str,
        implementations: Sequence[HookImpl],
        kwargs: Mapping[str, Any],
    ) -> None:
        assert outcome.exception is (error if raises else None)
        if not raises:
            assert outcome.get_result() == [42]
        outcome.force_result([99])

    def observe_result(
        outcome: Result[Any],
        name: str,
        implementations: Sequence[HookImpl],
        kwargs: Mapping[str, Any],
    ) -> None:
        observed.append(
            outcome.exception if outcome.exception is not None else outcome.get_result()
        )

    undo_replace = he_pm.add_hookcall_monitoring(lambda *args: None, replace_result)
    undo_observe = he_pm.add_hookcall_monitoring(lambda *args: None, observe_result)
    assert he_pm.hook.he_method1(arg=42) == [99]
    assert observed == [[99]]
    undo_replace()
    if raises:
        with pytest.raises(ValueError) as exc_info:
            he_pm.hook.he_method1(arg=42)
        assert exc_info.value is error
        assert observed == [[99], error]
    else:
        assert he_pm.hook.he_method1(arg=42) == [42]
        assert observed == [[99], [42]]
    undo_observe()


def test_removed_monitors_are_released(he_pm: PluginManager) -> None:
    he_pm.register(Plugin())
    events: list[str] = []

    class Before:
        def __call__(
            self,
            name: str,
            implementations: Sequence[HookImpl],
            kwargs: Mapping[str, Any],
        ) -> None:
            events.append("before")

    callbacks: list[weakref.ReferenceType[Before]] = []

    def add() -> Callable[[], None]:
        before = Before()
        callbacks.append(weakref.ref(before))
        return he_pm.add_hookcall_monitoring(before, lambda *args: None)

    for _ in range(100):
        undo_old = add()
        undo_new = add()
        assert he_pm.hook.he_method1(arg=42) == [42]
        assert events == ["before", "before"]
        events.clear()
        undo_old()
        undo_new()
    del undo_old, undo_new
    gc.collect()
    assert all(callback() is None for callback in callbacks)
    assert he_pm.hook.he_method1(arg=42) == [42]
    assert not events
