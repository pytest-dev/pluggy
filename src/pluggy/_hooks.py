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
from ._caller import HookCaller
from ._caller import HookRelay
from ._config import HookimplOpts
from ._config import HookspecOpts
from ._config import normalize_hookimpl_opts
from ._decorators import _Namespace
from ._decorators import HookimplMarker
from ._decorators import HookSpec
from ._decorators import HookspecMarker
from ._decorators import varnames
from ._implementation import _HookImplFunction
from ._implementation import _Plugin
from ._implementation import HookImpl


__all__ = [
    "HookspecOpts",
    "HookimplOpts",
    "normalize_hookimpl_opts",
    "HookspecMarker",
    "HookimplMarker",
    "HookSpec",
    "varnames",
    "HookCaller",
    "HookRelay",
    "_HookCaller",
    "_HookRelay",
    "_SubsetHookCaller",
    "HookImpl",
    "_HookImplFunction",
    "_Namespace",
    "_Plugin",
    "_HookExec",
]
