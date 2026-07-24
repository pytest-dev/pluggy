"""
Project configuration hub for pluggy projects.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from ._config import HookimplConfiguration
    from ._config import HookspecConfiguration
    from ._manager import PluginManager


class ProjectSpec:
    """Manages hook markers and plugin manager creation for a pluggy project.

    This class provides a unified interface for creating and managing the
    core components of a pluggy project: :class:`HookspecMarker`,
    :class:`HookimplMarker`, and :class:`PluginManager`.

    All components share the same ``project_name``, ensuring consistent
    behavior across hook specifications, implementations, and plugin
    management.

    :param project_name:
        The short project name. Prefer snake case. Make sure it's unique!
    :param plugin_manager_cls:
        Custom :class:`PluginManager` subclass to use (defaults to
        :class:`PluginManager`).

    .. versionadded:: 1.7
    """

    def __init__(
        self,
        project_name: str,
        plugin_manager_cls: type[PluginManager] | None = None,
    ) -> None:
        # Local imports to avoid circular imports with the marker and
        # manager modules.
        from ._decorators import HookimplMarker
        from ._decorators import HookspecMarker
        from ._manager import PluginManager as DefaultPluginManager

        #: The project name used across all components.
        self.project_name: Final = project_name
        self._plugin_manager_cls: Final = plugin_manager_cls or DefaultPluginManager

        # Marker instances are stateless decorators, safe to share.
        #: Hook specification marker for this project.
        self.hookspec: Final = HookspecMarker(self)
        #: Hook implementation marker for this project.
        self.hookimpl: Final = HookimplMarker(self)

    def create_plugin_manager(self) -> PluginManager:
        """Create a new :class:`PluginManager` instance for this project.

        Each call returns a fresh, independent instance configured with this
        project's name.
        """
        return self._plugin_manager_cls(self)

    def get_hookspec_config(
        self, func: Callable[..., object]
    ) -> HookspecConfiguration | None:
        """Extract the hook specification configuration from a decorated
        function, or ``None`` if it is not decorated with this project's
        hookspec marker."""
        attr_name = self.project_name + "_spec"
        return getattr(func, attr_name, None)

    def get_hookimpl_config(
        self, func: Callable[..., object]
    ) -> HookimplConfiguration | None:
        """Extract the hook implementation configuration from a decorated
        function, or ``None`` if it is not decorated with this project's
        hookimpl marker."""
        attr_name = self.project_name + "_impl"
        return getattr(func, attr_name, None)

    def __repr__(self) -> str:
        return f"ProjectSpec(project_name={self.project_name!r})"
