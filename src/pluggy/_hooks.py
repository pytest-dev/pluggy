"""
Internal hook annotation, representation and calling machinery.

This module re-exports symbols from the role-specific modules for
backward compatibility.
"""

from __future__ import annotations

from ._caller import _HookCaller
from ._caller import _HookExec
from ._caller import _HookRelay
from ._caller import _SubsetHookCaller
from ._caller import HistoricHookCaller
from ._caller import HookCaller
from ._caller import HookRelay
from ._caller import NormalHookCaller
from ._caller import SubsetHookCaller
from ._config import HookimplConfiguration
from ._config import HookspecConfiguration
from ._decorators import _Namespace
from ._decorators import HookimplMarker
from ._decorators import HookSpec
from ._decorators import HookspecMarker
from ._decorators import varnames
from ._impl import _HookImplFunction
from ._impl import _Plugin
from ._impl import CompletionHook
from ._impl import HookImpl
from ._impl import NormalImpl
from ._impl import WrapperImpl


__all__ = [
    "CompletionHook",
    "HistoricHookCaller",
    "HookCaller",
    "HookImpl",
    "HookRelay",
    "HookSpec",
    "HookimplConfiguration",
    "HookimplMarker",
    "HookspecConfiguration",
    "HookspecMarker",
    "NormalHookCaller",
    "NormalImpl",
    "SubsetHookCaller",
    "WrapperImpl",
    "_HookCaller",
    "_HookExec",
    "_HookImplFunction",
    "_HookRelay",
    "_Namespace",
    "_Plugin",
    "_SubsetHookCaller",
    "varnames",
]
