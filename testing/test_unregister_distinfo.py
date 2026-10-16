"""Regression coverage for pluggy issue #763.

``PluginManager.unregister`` removed the plugin from the hook callers and from
``_name2plugin`` but left its ``_plugin_distinfo`` entry behind. A plugin loaded
through entry points therefore kept appearing in ``list_plugin_distinfo()`` and
``list_plugin_distributions()`` after being unregistered, and re-registering it
appended a second entry for the same plugin.
"""

from __future__ import annotations

import importlib.metadata
from typing import cast

import pytest

from pluggy import PluginManager


def _install_entrypoint_dist(monkeypatch: pytest.MonkeyPatch, holder: dict) -> None:
    """Make importlib.metadata report one distribution with a single entry point."""

    class EntryPoint:
        name = "myname"
        group = "hello"
        value = "myname:foo"

        def load(self):
            holder["loads"] = holder.get("loads", 0) + 1
            return holder["plugin"]

    class Distribution:
        entry_points = (EntryPoint(),)

    dist = cast(importlib.metadata.Distribution, Distribution())
    monkeypatch.setattr(importlib.metadata, "distributions", lambda: (dist,))
    holder["dist"] = dist


def test_unregister_drops_the_plugin_distinfo_entry(
    monkeypatch: pytest.MonkeyPatch, pm: PluginManager
) -> None:
    """An unregistered entry-point plugin must not be listed any more."""
    holder: dict = {"plugin": type("PseudoPlugin", (), {})()}
    _install_entrypoint_dist(monkeypatch, holder)

    assert pm.load_setuptools_entrypoints("hello") == 1
    plugin = pm.get_plugin("myname")
    assert plugin is holder["plugin"]
    assert len(pm.list_plugin_distributions()) == 1
    assert len(pm.list_plugin_distinfo()) == 1

    assert pm.unregister(name="myname") is plugin

    assert pm.get_plugin("myname") is None
    assert pm.list_plugin_distributions() == []
    assert pm.list_plugin_distinfo() == []


def test_unregister_then_reregister_does_not_duplicate_distinfo(
    monkeypatch: pytest.MonkeyPatch, pm: PluginManager
) -> None:
    """Re-registering must not leave two entries for the same plugin."""
    holder: dict = {"plugin": type("PseudoPlugin", (), {})()}
    _install_entrypoint_dist(monkeypatch, holder)

    assert pm.load_setuptools_entrypoints("hello") == 1
    plugin = pm.get_plugin("myname")
    pm.unregister(name="myname")

    pm.register(plugin, name="myname")
    assert pm.list_plugin_distributions() == []
    assert pm.list_plugin_distinfo() == []

    # Reloading from the entry point re-appends exactly one entry.
    assert pm.unregister(name="myname") is plugin
    assert pm.load_setuptools_entrypoints("hello") == 1
    assert pm.list_plugin_distributions() == [(plugin, holder["dist"])]


def test_unregister_by_plugin_object_also_drops_distinfo(
    monkeypatch: pytest.MonkeyPatch, pm: PluginManager
) -> None:
    """The plugin-object form of unregister clears the bookkeeping too."""
    holder: dict = {"plugin": type("PseudoPlugin", (), {})()}
    _install_entrypoint_dist(monkeypatch, holder)

    assert pm.load_setuptools_entrypoints("hello") == 1
    plugin = pm.get_plugin("myname")

    assert pm.unregister(plugin=plugin) is plugin
    assert pm.list_plugin_distributions() == []
    assert pm.list_plugin_distinfo() == []
