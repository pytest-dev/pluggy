"""
Configuration types for hook specifications and implementations.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from typing import Final
from typing import final


@final
class HookspecConfiguration:
    """Configuration for a hook specification."""

    __slots__ = (
        "firstresult",
        "historic",
        "warn_on_impl",
        "warn_on_impl_args",
    )
    firstresult: Final[bool]
    historic: Final[bool]
    warn_on_impl: Final[Warning | None]
    warn_on_impl_args: Final[Mapping[str, Warning] | None]

    def __init__(
        self,
        firstresult: bool = False,
        historic: bool = False,
        warn_on_impl: Warning | None = None,
        warn_on_impl_args: Mapping[str, Warning] | None = None,
    ) -> None:
        if historic and firstresult:
            raise ValueError("cannot have a historic firstresult hook")
        #: Whether the hook is :ref:`first result only <firstresult>`.
        self.firstresult = firstresult
        #: Whether the hook is :ref:`historic <historic>`.
        self.historic = historic
        #: Whether the hook :ref:`warns when implemented <warn_on_impl>`.
        self.warn_on_impl = warn_on_impl
        #: Whether the hook warns when :ref:`certain arguments are requested
        #: <warn_on_impl>`.
        self.warn_on_impl_args = warn_on_impl_args

    def __repr__(self) -> str:
        attrs = [
            f"{slot}={getattr(self, slot)!r}"
            for slot in self.__slots__
            if getattr(self, slot)
        ]
        return f"HookspecConfiguration({', '.join(attrs)})"


@final
class HookimplConfiguration:
    """Configuration for a hook implementation."""

    __slots__ = (
        "wrapper",
        "hookwrapper",
        "optionalhook",
        "tryfirst",
        "trylast",
        "specname",
    )
    wrapper: Final[bool]
    hookwrapper: Final[bool]
    optionalhook: Final[bool]
    tryfirst: Final[bool]
    trylast: Final[bool]
    specname: Final[str | None]

    def __init__(
        self,
        wrapper: bool = False,
        hookwrapper: bool = False,
        optionalhook: bool = False,
        tryfirst: bool = False,
        trylast: bool = False,
        specname: str | None = None,
    ) -> None:
        #: Whether the hook implementation is a :ref:`wrapper <hookwrapper>`.
        self.wrapper = wrapper
        #: Whether the hook implementation is an :ref:`old-style wrapper
        #: <old_style_hookwrappers>`.
        self.hookwrapper = hookwrapper
        #: Whether validation against a hook specification is :ref:`optional
        #: <optionalhook>`.
        self.optionalhook = optionalhook
        #: Whether to try to order this hook implementation :ref:`first
        #: <callorder>`.
        self.tryfirst = tryfirst
        #: Whether to try to order this hook implementation :ref:`last
        #: <callorder>`.
        self.trylast = trylast
        #: The name of the hook specification to match, see :ref:`specname`.
        self.specname = specname

    def __repr__(self) -> str:
        attrs = [
            f"{slot}={getattr(self, slot)!r}"
            for slot in self.__slots__
            if getattr(self, slot)
        ]
        return f"HookimplConfiguration({', '.join(attrs)})"


def hookspec_config_from_mapping(
    opts: Mapping[str, Any],
) -> HookspecConfiguration:
    """Build a :class:`HookspecConfiguration` from a mapping.

    Intended for pytest/support migration only — not the public options API.
    Prefer constructing :class:`HookspecConfiguration` directly.
    """
    return HookspecConfiguration(
        firstresult=bool(opts.get("firstresult", False)),
        historic=bool(opts.get("historic", False)),
        warn_on_impl=opts.get("warn_on_impl"),
        warn_on_impl_args=opts.get("warn_on_impl_args"),
    )


def hookimpl_config_from_mapping(
    opts: Mapping[str, Any],
) -> HookimplConfiguration:
    """Build a :class:`HookimplConfiguration` from a mapping.

    Intended for pytest/support migration only — not the public options API.
    Prefer constructing :class:`HookimplConfiguration` directly.
    """
    return HookimplConfiguration(
        wrapper=bool(opts.get("wrapper", False)),
        hookwrapper=bool(opts.get("hookwrapper", False)),
        optionalhook=bool(opts.get("optionalhook", False)),
        tryfirst=bool(opts.get("tryfirst", False)),
        trylast=bool(opts.get("trylast", False)),
        specname=opts.get("specname"),
    )


def hookspec_config_to_mapping(
    config: HookspecConfiguration,
) -> dict[str, Any]:
    """Serialize configuration to a legacy mapping (pytest/support only)."""
    return {
        "firstresult": config.firstresult,
        "historic": config.historic,
        "warn_on_impl": config.warn_on_impl,
        "warn_on_impl_args": config.warn_on_impl_args,
    }


def hookimpl_config_to_mapping(
    config: HookimplConfiguration,
) -> dict[str, Any]:
    """Serialize configuration to a legacy mapping (pytest/support only)."""
    return {
        "wrapper": config.wrapper,
        "hookwrapper": config.hookwrapper,
        "optionalhook": config.optionalhook,
        "tryfirst": config.tryfirst,
        "trylast": config.trylast,
        "specname": config.specname,
    }
