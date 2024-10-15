"""this module contains importlib_metadata usage and importing

it's deferred to avoid import-time dependency on importlib_metadata

.. code-block:: console

   python -X importtime -c 'import pluggy' 2> import0.log
   tuna import0.log


"""

from __future__ import annotations

import importlib.metadata
from typing import Any

from . import _manager


class DistFacade:
    """Emulate a pkg_resources Distribution"""

    def __init__(self, dist: importlib.metadata.Distribution) -> None:
        self._dist = dist

    @property
    def project_name(self) -> str:
        name: str = self.metadata["name"]
        return name

    def __getattr__(self, attr: str, default: object | None = None) -> Any:
        return getattr(self._dist, attr, default)

    def __dir__(self) -> list[str]:
        return sorted(dir(self._dist) + ["_dist", "project_name"])


def load_importlib_entrypoints(
    manager: _manager.PluginManager,
    group: str,
    name: str | None = None,
) -> int:
    """Load modules from querying the specified setuptools ``group``.

    :param group:
        Entry point group to load plugins.
    :param name:
        If given, loads only plugins with the given ``name``.

    :return:
        The number of plugins loaded by this call.
    """
    count = 0
    for dist in list(importlib.metadata.distributions()):
        for ep in dist.entry_points:
            if (
                ep.group != group
                or (name is not None and ep.name != name)
                # already registered
                or manager.get_plugin(ep.name)
                or manager.is_blocked(ep.name)
            ):
                continue
            plugin = ep.load()
            manager.register(plugin, name=ep.name)
            manager._plugin_dist_metadata.append((plugin, dist))
            count += 1
    return count
