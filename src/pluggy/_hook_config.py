"""
Hook configuration classes and type definitions.
"""

from __future__ import annotations

from collections.abc import Generator
from collections.abc import Mapping
from collections.abc import Sequence
from types import ModuleType
from typing import Callable
from typing import Final
from typing import final
from typing import Protocol
from typing import TypedDict
from typing import TypeVar
from typing import Union

from . import _hook_callers  # import as partial module for forward refs
from ._result import Result


_T = TypeVar("_T")
_F = TypeVar("_F", bound=Callable[..., object])
_Namespace = Union[ModuleType, type]
_Plugin = object


class _HookExec(Protocol):
    def __call__(
        self,
        hook_name: str,
        normal_impls: Sequence[_hook_callers.HookImpl],
        wrapper_impls: Sequence[_hook_callers.WrapperImpl],
        caller_kwargs: Mapping[str, object],
        firstresult: bool,
    ) -> object | list[object]: ...


_HookImplFunction = Callable[..., Union[_T, Generator[None, Result[_T], None]]]


class HookspecOpts(TypedDict):
    """Options for a hook specification."""

    #: Whether the hook is :ref:`first result only <firstresult>`.
    firstresult: bool
    #: Whether the hook is :ref:`historic <historic>`.
    historic: bool
    #: Whether the hook :ref:`warns when implemented <warn_on_impl>`.
    warn_on_impl: Warning | None
    #: Whether the hook warns when :ref:`certain arguments are requested
    #: <warn_on_impl>`.
    #:
    #: .. versionadded:: 1.5
    warn_on_impl_args: Mapping[str, Warning] | None


class HookimplOpts(TypedDict):
    """Options for a hook implementation."""

    #: Whether the hook implementation is a :ref:`wrapper <hookwrapper>`.
    wrapper: bool
    #: Whether the hook implementation is an :ref:`old-style wrapper
    #: <old_style_hookwrappers>`.
    hookwrapper: bool
    #: Whether validation against a hook specification is :ref:`optional
    #: <optionalhook>`.
    optionalhook: bool
    #: Whether to try to order this hook implementation :ref:`first
    #: <callorder>`.
    tryfirst: bool
    #: Whether to try to order this hook implementation :ref:`last
    #: <callorder>`.
    trylast: bool
    #: The name of the hook specification to match, see :ref:`specname`.
    specname: str | None


@final
class HookspecConfiguration:
    """Configuration class for hook specifications.

    This class is intended to replace HookspecOpts in future versions.
    It provides a more structured and extensible way to configure hook specifications.
    """

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
        """Initialize hook specification configuration.

        :param firstresult:
            Whether the hook is :ref:`first result only <firstresult>`.
        :param historic:
            Whether the hook is :ref:`historic <historic>`.
        :param warn_on_impl:
            Whether the hook :ref:`warns when implemented <warn_on_impl>`.
        :param warn_on_impl_args:
            Whether the hook warns when :ref:`certain arguments are requested
            <warn_on_impl>`.
        """
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
        attrs = []
        for slot in self.__slots__:
            value = getattr(self, slot)
            if value:
                attrs.append(f"{slot}={value!r}")
        attrs_str = ", ".join(attrs)
        return f"HookspecConfiguration({attrs_str})"


@final
class HookimplConfiguration:
    """Configuration class for hook implementations.

    This class is intended to replace HookimplOpts in future versions.
    It provides a more structured and extensible way to configure hook implementations.
    """

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
        """Initialize hook implementation configuration.

        :param wrapper:
            Whether the hook implementation is a :ref:`wrapper <hookwrapper>`.
        :param hookwrapper:
            Whether the hook implementation is an :ref:`old-style wrapper
            <old_style_hookwrappers>`.
        :param optionalhook:
            Whether validation against a hook specification is :ref:`optional
            <optionalhook>`.
        :param tryfirst:
            Whether to try to order this hook implementation :ref:`first
            <callorder>`.
        :param trylast:
            Whether to try to order this hook implementation :ref:`last
            <callorder>`.
        :param specname:
            The name of the hook specification to match, see :ref:`specname`.
        """
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

    def create_hookimpl(
        self,
        plugin: _Plugin,
        plugin_name: str,
        function: _HookImplFunction[object],
    ) -> _hook_callers.HookImpl | _hook_callers.WrapperImpl:
        """Create the appropriate HookImpl subclass based on configuration."""
        if self.wrapper or self.hookwrapper:
            return _hook_callers.WrapperImpl(plugin, plugin_name, function, self)
        else:
            return _hook_callers.HookImpl(plugin, plugin_name, function, self)

    def __repr__(self) -> str:
        attrs = []
        for slot in self.__slots__:
            value = getattr(self, slot)
            if value:
                attrs.append(f"{slot}={value!r}")
        attrs_str = ", ".join(attrs)
        return f"HookimplConfiguration({attrs_str})"
