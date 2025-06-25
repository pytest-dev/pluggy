"""
Backward compatibility re-exports for hook functionality.

This module re-exports all hook-related classes and functions from their
new organized modules to maintain backward compatibility.
"""

# Configuration classes and types
from ._hook_callers import _HookCaller
from ._hook_callers import _HookRelay
from ._hook_callers import _SubsetHookCaller
from ._hook_callers import HistoricHookCaller

# Hook callers and implementations
from ._hook_callers import HookCaller
from ._hook_callers import HookImpl
from ._hook_callers import HookRelay
from ._hook_callers import NormalHookCaller
from ._hook_callers import SubsetHookCaller
from ._hook_config import HookimplConfiguration
from ._hook_config import HookimplOpts
from ._hook_config import HookspecConfiguration
from ._hook_config import HookspecOpts
from ._hook_markers import HookimplMarker
from ._hook_markers import HookSpec

# Hook markers and specifications
from ._hook_markers import HookspecMarker
from ._hook_markers import varnames


# Re-export all public symbols for backward compatibility
__all__ = [
    # Configuration
    "HookspecOpts",
    "HookimplOpts",
    "HookspecConfiguration",
    "HookimplConfiguration",
    # Markers and specifications
    "HookspecMarker",
    "HookimplMarker",
    "HookSpec",
    "varnames",
    # Callers and implementations
    "HookCaller",
    "HookRelay",
    "_HookRelay",
    "HistoricHookCaller",
    "NormalHookCaller",
    "_HookCaller",
    "SubsetHookCaller",
    "_SubsetHookCaller",
    "HookImpl",
]
