__all__ = [
    "__version__",
    "PluginManager",
    "PluginValidationError",
    "HookCaller",
    "HistoricHookCaller",
    "HookCallError",
    "HookspecOpts",
    "HookimplOpts",
    "HookspecConfiguration",
    "HookimplConfiguration",
    "HookImpl",
    "HookRelay",
    "HookspecMarker",
    "HookimplMarker",
    "ProjectSpec",
    "Result",
    "PluggyWarning",
    "PluggyTeardownRaisedWarning",
]
from ._hook_callers import HistoricHookCaller
from ._hook_callers import HookCaller
from ._hook_callers import HookImpl
from ._hook_callers import HookRelay
from ._hook_config import HookimplConfiguration
from ._hook_config import HookimplOpts
from ._hook_config import HookspecConfiguration
from ._hook_config import HookspecOpts
from ._hook_markers import HookimplMarker
from ._hook_markers import HookspecMarker
from ._manager import PluginManager
from ._manager import PluginValidationError
from ._project import ProjectSpec
from ._result import HookCallError
from ._result import Result
from ._warnings import PluggyTeardownRaisedWarning
from ._warnings import PluggyWarning


__version__: str


def __getattr__(name: str) -> str:
    if name == "__version__":
        from importlib.metadata import version

        return version("pluggy")

    raise AttributeError(f"module {__name__} has no attribute {name!r}")
