__all__ = [
    "__version__",
    "PluginManager",
    "PluginValidationError",
    "HookCaller",
    "HookCallError",
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
from ._hooks import HookCaller
from ._hooks import HookImpl
from ._hooks import HookimplMarker
from ._hooks import HookRelay
from ._hooks import HookspecMarker
from ._manager import PluginManager
from ._manager import PluginValidationError
from ._result import HookCallError
from ._result import Result
from ._version import version as __version__
from ._warnings import PluggyTeardownRaisedWarning
from ._warnings import PluggyWarning


TYPE_CHECKING = False
if TYPE_CHECKING:
    from ._types import HookimplOpts
    from ._types import HookspecOpts
else:

    def __getattr__(name: str) -> object:
        if name.endswith("Opts"):
            from . import _types

            return getattr(_types, name)
        raise AttributeError(name)
