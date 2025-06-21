__all__ = [
    "__version__",
    "PluginManager",
    "PluginValidationError",
    "HookCaller",
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
from ._hooks import HookCaller
from ._hooks import HookImpl
from ._hooks import HookimplConfiguration
from ._hooks import HookimplMarker
from ._hooks import HookimplOpts
from ._hooks import HookRelay
from ._hooks import HookspecConfiguration
from ._hooks import HookspecMarker
from ._hooks import HookspecOpts
from ._manager import PluginManager
from ._manager import PluginValidationError
from ._project import ProjectSpec
from ._result import HookCallError
from ._result import Result
from ._warnings import PluggyTeardownRaisedWarning
from ._warnings import PluggyWarning


def __getattr__(name: str) -> str:
    if name == "__version__":
        from importlib.metadata import version

        return version("pluggy")

    raise AttributeError(f"module {__name__} has no attribute {name!r}")
