from collections.abc import Callable

import pytest

from pluggy import HookimplMarker
from pluggy import HookspecMarker
from pluggy import PluginManager


@pytest.mark.parametrize("undo_newer", [False, True], ids=["keep-newer", "remove-both"])
def test_monitoring_undo_out_of_order(undo_newer: bool) -> None:
    """Undo must remove only its own monitor, without reviving removed ones."""
    hookspec = HookspecMarker("example")
    hookimpl = HookimplMarker("example")

    class Spec:
        @hookspec
        def hello(self) -> None:
            """Return a greeting."""

    class Plugin:
        @hookimpl
        def hello(self) -> int:
            return 1

    pm = PluginManager("example")
    pm.add_hookspecs(Spec)
    pm.register(Plugin())
    events: list[str] = []

    def monitor(label: str) -> Callable[[], None]:
        def before(*args: object) -> None:
            events.append(f"before {label}")

        def after(*args: object) -> None:
            events.append(f"after {label}")

        return pm.add_hookcall_monitoring(before, after)

    undo_a = monitor("A")
    undo_b = monitor("B")
    assert pm.hook.hello() == [1]
    assert events == ["before B", "before A", "after A", "after B"]
    events.clear()

    undo_a()
    if undo_newer:
        undo_b()

    assert pm.hook.hello() == [1]
    assert events == ([] if undo_newer else ["before B", "after B"])

    events.clear()
    undo_a()
    assert pm.hook.hello() == [1]
    assert events == ([] if undo_newer else ["before B", "after B"])
