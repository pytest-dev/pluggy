__all__ = [
    "__version__",
    "PluginManager",
    "PluginValidationError",
    "HookCaller",
    "HookCallError",
    "HookspecConfiguration",
    "HookimplConfiguration",
    "HookspecOpts",
    "HookimplOpts",
    "HookImpl",
    "HookRelay",
    "HookspecMarker",
    "HookimplMarker",
    "Result",
    "PluggyWarning",
    "PluggyTeardownRaisedWarning",
]
from ._config import HookimplConfiguration
from ._config import HookspecConfiguration
from ._hooks import HookCaller
from ._hooks import HookImpl
from ._hooks import HookimplMarker
from ._hooks import HookRelay
from ._hooks import HookspecMarker
from ._manager import PluginManager
from ._manager import PluginValidationError
from ._pytest_compat import HookimplOpts
from ._pytest_compat import HookspecOpts
from ._result import HookCallError
from ._result import Result
from ._warnings import PluggyTeardownRaisedWarning
from ._warnings import PluggyWarning


def __getattr__(name: str) -> str:
    if name == "__version__":
        from importlib.metadata import version

        return version("pluggy")

    raise AttributeError(f"module {__name__} has no attribute {name!r}")
