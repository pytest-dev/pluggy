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
from ._implementation import _HookImplFunction
from ._implementation import _Plugin
from ._implementation import CompletionHook
from ._implementation import HookImpl
from ._implementation import NormalImpl
from ._implementation import WrapperImpl


__all__ = [
    "HookspecConfiguration",
    "HookimplConfiguration",
    "HookspecMarker",
    "HookimplMarker",
    "HookSpec",
    "varnames",
    "HookCaller",
    "NormalHookCaller",
    "HistoricHookCaller",
    "SubsetHookCaller",
    "HookRelay",
    "_HookCaller",
    "_HookRelay",
    "_SubsetHookCaller",
    "HookImpl",
    "NormalImpl",
    "WrapperImpl",
    "CompletionHook",
    "_HookImplFunction",
    "_Namespace",
    "_Plugin",
    "_HookExec",
]
