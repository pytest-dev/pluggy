"""
Project configuration and management for pluggy projects.
"""

from __future__ import annotations

from typing import Callable
from typing import Final
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from ._hook_config import HookimplConfiguration
    from ._hook_config import HookspecConfiguration
    from ._manager import PluginManager


class ProjectSpec:
    """Manages hook markers and plugin manager creation for a pluggy project.

    This class provides a unified interface for creating and managing the core
    components of a pluggy project: HookspecMarker, HookimplMarker, and PluginManager.

    All components share the same project_name, ensuring consistent behavior
    across hook specifications, implementations, and plugin management.

    :param project_name:
        The short project name. Prefer snake case. Make sure it's unique!
    :param plugin_manager_cls:
        Custom PluginManager subclass to use (defaults to PluginManager).
    """

    def __init__(
        self, project_name: str, plugin_manager_cls: type[PluginManager] | None = None
    ) -> None:
        from ._hook_markers import HookimplMarker
        from ._hook_markers import HookspecMarker
        from ._manager import PluginManager as DefaultPluginManager

        #: The project name used across all components.
        self.project_name: Final = project_name
        #: The PluginManager class for creating new instances.
        self._plugin_manager_cls: Final = plugin_manager_cls or DefaultPluginManager

        # Create marker instances (these are stateless decorators, safe to share)
        #: Hook specification marker for decorating hook specification functions.
        self.hookspec: Final = HookspecMarker(self)
        #: Hook implementation marker for decorating hook implementation functions.
        self.hookimpl: Final = HookimplMarker(self)

    def create_plugin_manager(self) -> PluginManager:
        """Create a new PluginManager instance for this project.

        Each call returns a fresh, independent PluginManager instance
        configured with this project's name and using the specified
        PluginManager class (if provided during initialization).

        :returns: New PluginManager instance.
        """
        return self._plugin_manager_cls(self)

    def get_hookspec_config(
        self, func: Callable[..., object]
    ) -> HookspecConfiguration | None:
        """Extract hook specification configuration from a decorated function.

        :param func: A function that may be decorated with this project's
            hookspec marker
        :return: HookspecConfiguration object if found, None if not decorated
            with this project's hookspec marker
        """
        attr_name = self.project_name + "_spec"
        return getattr(func, attr_name, None)

    def get_hookimpl_config(
        self, func: Callable[..., object]
    ) -> HookimplConfiguration | None:
        """Extract hook implementation configuration from a decorated function.

        :param func: A function that may be decorated with this project's
            hookimpl marker
        :return: HookimplConfiguration object if found, None if not decorated
            with this project's hookimpl marker
        """
        attr_name = self.project_name + "_impl"
        return getattr(func, attr_name, None)

    def __repr__(self) -> str:
        return f"ProjectSpec(project_name={self.project_name!r})"
