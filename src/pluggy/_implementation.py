"""
Hook implementation representation.
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Generator
from collections.abc import Mapping
from typing import cast
from typing import Final
from typing import final
from typing import Protocol
from typing import runtime_checkable
from typing import TypeAlias
from typing import TypeVar

from ._config import HookimplConfiguration
from ._decorators import varnames
from ._result import HookCallError
from ._result import Result


_T = TypeVar("_T")

_Plugin: TypeAlias = object
_HookImplFunction: TypeAlias = Callable[..., _T | Generator[None, Result[_T], None]]


@runtime_checkable
class CompletionHook(Protocol):
    """Teardown callback returned by :meth:`WrapperImpl.setup_and_get_completion_hook`.

    Receives the current ``(result, exception)`` outcome of the hook call and
    returns the possibly replaced ``(result, exception)`` pair.
    """

    def __call__(
        self,
        result: object | list[object] | None,
        exception: BaseException | None,
    ) -> tuple[object | list[object] | None, BaseException | None]: ...


class HookImpl:
    """Base class for hook implementations in a :class:`HookCaller`."""

    __slots__ = (
        "function",
        "argnames",
        "kwargnames",
        "plugin",
        "hookimpl_config",
        "plugin_name",
        "wrapper",
        "hookwrapper",
        "optionalhook",
        "tryfirst",
        "trylast",
    )

    def __init__(
        self,
        plugin: _Plugin,
        plugin_name: str,
        function: _HookImplFunction[object],
        hook_impl_config: HookimplConfiguration,
    ) -> None:
        """:meta private:"""
        #: The hook implementation function.
        self.function: Final = function
        argnames, kwargnames = varnames(self.function)
        #: The positional parameter names of ``function```.
        self.argnames: Final = argnames
        #: The keyword parameter names of ``function```.
        self.kwargnames: Final = kwargnames
        #: The plugin which defined this hook implementation.
        self.plugin: Final = plugin
        #: The :class:`HookimplConfiguration` used to configure this hook
        #: implementation.
        self.hookimpl_config: Final = hook_impl_config
        #: The name of the plugin which defined this hook implementation.
        self.plugin_name: Final = plugin_name
        #: Whether the hook implementation is a :ref:`wrapper <hookwrapper>`.
        self.wrapper: Final = hook_impl_config.wrapper
        #: Whether the hook implementation is an :ref:`old-style wrapper
        #: <old_style_hookwrappers>`.
        self.hookwrapper: Final = hook_impl_config.hookwrapper
        #: Whether validation against a hook specification is :ref:`optional
        #: <optionalhook>`.
        self.optionalhook: Final = hook_impl_config.optionalhook
        #: Whether to try to order this hook implementation :ref:`first
        #: <callorder>`.
        self.tryfirst: Final = hook_impl_config.tryfirst
        #: Whether to try to order this hook implementation :ref:`last
        #: <callorder>`.
        self.trylast: Final = hook_impl_config.trylast

    @property
    def opts(self) -> HookimplConfiguration:
        """Alias for :attr:`hookimpl_config`.

        .. deprecated::
            Use :attr:`hookimpl_config` instead.
        """
        return self.hookimpl_config

    def _get_call_args(self, caller_kwargs: Mapping[str, object]) -> list[object]:
        """Extract the positional arguments for calling this hook implementation.

        :raises HookCallError: If a required argument is missing.
        """
        try:
            return [caller_kwargs[argname] for argname in self.argnames]
        except KeyError as e:
            raise HookCallError(f"hook call must provide argument {e.args[0]!r}") from e

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} "
            f"plugin_name={self.plugin_name!r}, plugin={self.plugin!r}>"
        )


@final
class NormalImpl(HookImpl):
    """A normal (non-wrapper) hook implementation in a :class:`HookCaller`."""

    def __init__(
        self,
        plugin: _Plugin,
        plugin_name: str,
        function: _HookImplFunction[object],
        hook_impl_config: HookimplConfiguration,
    ) -> None:
        """:meta private:"""
        if hook_impl_config.wrapper or hook_impl_config.hookwrapper:
            raise ValueError(
                "NormalImpl cannot be used for wrapper implementations. "
                "Use WrapperImpl instead."
            )
        super().__init__(plugin, plugin_name, function, hook_impl_config)


@final
class WrapperImpl(HookImpl):
    """A wrapper hook implementation in a :class:`HookCaller`."""

    def __init__(
        self,
        plugin: _Plugin,
        plugin_name: str,
        function: _HookImplFunction[object],
        hook_impl_config: HookimplConfiguration,
    ) -> None:
        """:meta private:"""
        if not (hook_impl_config.wrapper or hook_impl_config.hookwrapper):
            raise ValueError(
                "WrapperImpl can only be used for wrapper implementations. "
                "Use NormalImpl for normal implementations."
            )
        super().__init__(plugin, plugin_name, function, hook_impl_config)

    def setup_and_get_completion_hook(
        self, hook_name: str, caller_kwargs: Mapping[str, object]
    ) -> CompletionHook:
        """Run the wrapper setup phase and return its :class:`CompletionHook`.

        Old-style hookwrappers and new-style wrappers are handled uniformly by
        adapting old-style wrappers via ``run_old_style_hookwrapper``.

        The returned completion hook performs the teardown: it sends the
        current outcome into the wrapper generator (or throws the current
        exception) and returns the possibly replaced ``(result, exception)``
        pair.
        """
        # Local import to avoid a circular import with the execution module.
        from ._execution import _raise_wrapfail
        from ._execution import run_old_style_hookwrapper

        args = self._get_call_args(caller_kwargs)

        wrapper_gen: Generator[None, object, object]
        if self.hookwrapper:
            wrapper_gen = run_old_style_hookwrapper(self, hook_name, args)
        else:
            wrapper_gen = cast(Generator[None, object, object], self.function(*args))

        try:
            next(wrapper_gen)  # first yield / setup phase
        except StopIteration:
            _raise_wrapfail(wrapper_gen, "did not yield")

        def completion_hook(
            result: object | list[object] | None, exception: BaseException | None
        ) -> tuple[object | list[object] | None, BaseException | None]:
            try:
                if exception is not None:
                    try:
                        wrapper_gen.throw(exception)
                    except RuntimeError as re:
                        # StopIteration from generator causes RuntimeError
                        # even for coroutine usage - see #544
                        if (
                            isinstance(exception, StopIteration)
                            and re.__cause__ is exception
                        ):
                            wrapper_gen.close()
                            return result, exception
                        else:
                            raise
                else:
                    wrapper_gen.send(result)
                # Following is unreachable for a well behaved hook wrapper.
                # Try to force finalizers otherwise postponed till GC action.
                # Note: close() may raise if generator handles GeneratorExit.
                wrapper_gen.close()
                _raise_wrapfail(wrapper_gen, "has second yield")
            except StopIteration as si:
                return si.value, None
            except BaseException as e:
                return result, e

        return completion_hook
