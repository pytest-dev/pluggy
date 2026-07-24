"""Pytest/support compatibility helpers for legacy option encodings.

The live pluggy API uses :class:`~pluggy.HookspecConfiguration` and
:class:`~pluggy.HookimplConfiguration`. This module keeps TypedDict shapes and
mapping conversion for pytest and other callers that still type or attach
dict-shaped options during migration.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict

from ._config import hookimpl_config_from_mapping
from ._config import HookimplConfiguration
from ._config import hookspec_config_from_mapping
from ._config import HookspecConfiguration


class HookspecOpts(TypedDict):
    """Legacy TypedDict for hook specification options.

    Prefer :class:`~pluggy.HookspecConfiguration`. Kept for pytest/typing
    compatibility during migration.
    """

    firstresult: bool
    historic: bool
    warn_on_impl: Warning | None
    warn_on_impl_args: Mapping[str, Warning] | None


class HookimplOpts(TypedDict):
    """Legacy TypedDict for hook implementation options.

    Prefer :class:`~pluggy.HookimplConfiguration`. Kept for pytest/typing
    compatibility during migration.
    """

    wrapper: bool
    hookwrapper: bool
    optionalhook: bool
    tryfirst: bool
    trylast: bool
    specname: str | None


__all__ = [
    "HookspecOpts",
    "HookimplOpts",
    "HookspecConfiguration",
    "HookimplConfiguration",
    "hookspec_config_from_mapping",
    "hookimpl_config_from_mapping",
]
