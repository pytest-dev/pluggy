"""
Hook caller implementations and hook implementation classes.
"""

from __future__ import annotations

from collections.abc import Generator
from collections.abc import Mapping
from collections.abc import MutableSequence
from collections.abc import Sequence
from collections.abc import Set
from typing import Any
from typing import Callable
from typing import cast
from typing import Final
from typing import final
from typing import Optional
from typing import Protocol
from typing import runtime_checkable
from typing import TYPE_CHECKING
from typing import TypeVar

from ._hook_config import _HookExec
from ._hook_config import _HookImplFunction
from ._hook_config import _Namespace
from ._hook_config import _Plugin
from ._hook_config import HookimplConfiguration
from ._hook_config import HookspecConfiguration
from ._hook_config import HookspecOpts
from ._hook_markers import HookSpec
from ._hook_markers import varnames
from ._result import HookCallError


_T_HookImpl = TypeVar("_T_HookImpl", bound="HookImpl")

# Type alias for completion hook functions
CompletionHook = Callable[
    [object | list[object] | None, BaseException | None],
    tuple[object | list[object] | None, BaseException | None],
]


def _insert_hookimpl_into_list(
    hookimpl: _T_HookImpl, target_list: MutableSequence[_T_HookImpl]
) -> None:
    """Insert a hookimpl into the target list maintaining proper ordering.

    The ordering is: [trylast, normal, tryfirst]
    """
    if hookimpl.trylast:
        target_list.insert(0, hookimpl)
    elif hookimpl.tryfirst:
        target_list.append(hookimpl)
    else:
        # find last non-tryfirst method
        i = len(target_list) - 1
        while i >= 0 and target_list[i].tryfirst:
            i -= 1
        target_list.insert(i + 1, hookimpl)


@runtime_checkable
class HookCaller(Protocol):
    """Protocol defining the interface for hook callers."""

    @property
    def name(self) -> str:
        """Name of the hook getting called."""
        ...

    @property
    def spec(self) -> HookSpec | None:
        """The hook specification, if any."""
        ...

    def has_spec(self) -> bool:
        """Whether this caller has a hook specification."""
        ...

    def is_historic(self) -> bool:
        """Whether this caller is historic."""
        ...

    def get_hookimpls(self) -> list[HookImpl]:
        """Get all registered hook implementations for this hook."""
        ...

    def set_specification(
        self,
        specmodule_or_class: _Namespace,
        _spec_opts_or_config: HookspecOpts | HookspecConfiguration | None = None,
        *,
        spec_opts: HookspecOpts | None = None,
        spec_config: HookspecConfiguration | None = None,
    ) -> None:
        """Set the hook specification."""
        ...

    def __call__(self, **kwargs: object) -> Any:
        """Call the hook with given kwargs."""
        ...

    def call_historic(
        self,
        result_callback: Callable[[Any], None] | None = None,
        kwargs: Mapping[str, object] | None = None,
    ) -> None:
        """Call the hook historically."""
        ...

    def call_extra(
        self, methods: Sequence[Callable[..., object]], kwargs: Mapping[str, object]
    ) -> Any:
        """Call the hook with additional methods."""
        ...

    def __repr__(self) -> str:
        """String representation of the hook caller."""
        ...


@final
class HookRelay:
    """Hook holder object for performing 1:N hook calls where N is the number
    of registered plugins."""

    __slots__ = ("__dict__",)
    __dict__: dict[str, NormalHookCaller | HistoricHookCaller]

    def __init__(self) -> None:
        """:meta private:"""

    if TYPE_CHECKING:

        def __getattr__(self, name: str) -> NormalHookCaller | HistoricHookCaller: ...


# Historical name (pluggy<=1.2), kept for backward compatibility.
_HookRelay = HookRelay


_CallHistory = list[tuple[Mapping[str, object], Optional[Callable[[Any], None]]]]


class HistoricHookCaller:
    """A caller for historic hook specifications that memorizes and replays calls.

    Historic hooks memorize every call and replay them on plugins registered
    after the call was made. Historic hooks do not support wrappers.
    """

    __slots__ = (
        "name",
        "spec",
        "_hookexec",
        "_hookimpls",
        "_call_history",
    )
    name: Final[str]
    spec: Final[HookSpec]
    _hookexec: Final[_HookExec]
    _hookimpls: Final[list[HookImpl]]
    _call_history: Final[_CallHistory]

    def __init__(
        self,
        name: str,
        hook_execute: _HookExec,
        specmodule_or_class: _Namespace,
        spec_config: HookspecConfiguration,
    ) -> None:
        """:meta private:"""
        assert spec_config.historic, "HistoricHookCaller requires historic=True"
        #: Name of the hook getting called.
        self.name = name
        self._hookexec = hook_execute
        # The hookimpls list for historic hooks (no wrappers supported)
        self._hookimpls = []
        self._call_history = []
        # TODO: Document, or make private.
        self.spec = HookSpec(specmodule_or_class, name, spec_config)

    def has_spec(self) -> bool:
        return True  # HistoricHookCaller always has a spec

    def set_specification(
        self,
        specmodule_or_class: _Namespace,
        _spec_opts_or_config: HookspecOpts | HookspecConfiguration | None = None,
        *,
        spec_opts: HookspecOpts | None = None,
        spec_config: HookspecConfiguration | None = None,
    ) -> None:
        """Historic hooks cannot have their specification changed after creation."""
        raise ValueError(
            f"HistoricHookCaller {self.name!r} already has a specification. "
            "Historic hooks cannot have their specification changed."
        )

    def is_historic(self) -> bool:
        """Whether this caller is :ref:`historic <historic>`."""
        return True  # HistoricHookCaller is always historic

    def _remove_plugin(self, plugin: _Plugin) -> None:
        for i, method in enumerate(self._hookimpls):
            if method.plugin == plugin:
                del self._hookimpls[i]
                return
        raise ValueError(f"plugin {plugin!r} not found")

    def get_hookimpls(self) -> list[HookImpl]:
        """Get all registered hook implementations for this hook."""
        return cast(list[HookImpl], [*self._hookimpls])

    def _add_hookimpl(self, hookimpl: HookImpl) -> None:
        """Add an implementation to the callback chain."""
        # Historic hooks don't support wrappers - simpler ordering
        _insert_hookimpl_into_list(hookimpl, self._hookimpls)

        # Apply history to the newly added hookimpl
        self._maybe_apply_history(hookimpl)

    def __repr__(self) -> str:
        return f"<HistoricHookCaller {self.name!r}>"

    def __call__(self, **kwargs: object) -> Any:
        """Call the hook.

        Historic hooks cannot be called directly. Use call_historic instead.
        """
        raise RuntimeError(
            "Cannot directly call a historic hook - use call_historic instead."
        )

    def call_historic(
        self,
        result_callback: Callable[[Any], None] | None = None,
        kwargs: Mapping[str, object] | None = None,
    ) -> None:
        """Call the hook with given ``kwargs`` for all registered plugins and
        for all plugins which will be registered afterwards, see
        :ref:`historic`.

        :param result_callback:
            If provided, will be called for each non-``None`` result obtained
            from a hook implementation.
        """
        kwargs = kwargs or {}
        self.spec.verify_all_args_are_provided(kwargs)
        self._call_history.append((kwargs, result_callback))
        # Historizing hooks don't return results.
        # Remember firstresult isn't compatible with historic.
        # Copy because plugins may register other plugins during iteration (#438).
        res = self._hookexec(self.name, self._hookimpls.copy(), [], kwargs, False)
        if result_callback is None:
            return
        if isinstance(res, list):
            for x in res:
                result_callback(x)

    def call_extra(
        self, methods: Sequence[Callable[..., object]], kwargs: Mapping[str, object]
    ) -> Any:
        """Call the hook with some additional temporarily participating
        methods using the specified ``kwargs`` as call parameters, see
        :ref:`call_extra`."""
        raise RuntimeError(
            "Cannot call call_extra on a historic hook - use call_historic instead."
        )

    def _maybe_apply_history(self, method: HookImpl) -> None:
        """Apply call history to a new hookimpl if it is marked as historic."""
        for kwargs, result_callback in self._call_history:
            res = self._hookexec(self.name, [method], [], kwargs, False)
            if res and result_callback is not None:
                # XXX: remember firstresult isn't compat with historic
                assert isinstance(res, list)
                result_callback(res[0])


class NormalHookCaller:
    """A caller of all registered implementations of a hook specification."""

    __slots__ = (
        "name",
        "spec",
        "_hookexec",
        "_normal_hookimpls",
        "_wrapper_hookimpls",
    )
    name: Final[str]
    spec: HookSpec | None
    _hookexec: Final[_HookExec]
    _normal_hookimpls: Final[list[HookImpl]]
    _wrapper_hookimpls: Final[list[WrapperImpl]]

    def __init__(
        self,
        name: str,
        hook_execute: _HookExec,
        specmodule_or_class: _Namespace | None = None,
        spec_config: HookspecConfiguration | None = None,
    ) -> None:
        """:meta private:"""
        #: Name of the hook getting called.
        self.name = name
        self._hookexec = hook_execute
        # Split hook implementations into two lists for simpler management:
        # Normal hooks: [trylast, normal, tryfirst]
        # Wrapper hooks: [trylast, normal, tryfirst]
        # Combined execution order: normal_hooks + wrapper_hooks (reversed)
        self._normal_hookimpls = []
        self._wrapper_hookimpls = []
        # TODO: Document, or make private.
        self.spec: HookSpec | None = None
        if specmodule_or_class is not None:
            assert spec_config is not None
            self.set_specification(specmodule_or_class, spec_config=spec_config)

    # TODO: Document, or make private.
    def has_spec(self) -> bool:
        return self.spec is not None

    # TODO: Document, or make private.
    def set_specification(
        self,
        specmodule_or_class: _Namespace,
        _spec_opts_or_config: HookspecOpts | HookspecConfiguration | None = None,
        *,
        spec_opts: HookspecOpts | None = None,
        spec_config: HookspecConfiguration | None = None,
    ) -> None:
        if self.spec is not None:
            raise ValueError(
                f"Hook {self.spec.name!r} is already registered "
                f"within namespace {self.spec.namespace}"
            )

        # Handle the dual parameter - set the appropriate typed parameter
        if _spec_opts_or_config is not None:
            assert spec_opts is None and spec_config is None, (
                "Cannot provide both positional and keyword spec arguments"
            )

            if isinstance(_spec_opts_or_config, dict):
                spec_opts = _spec_opts_or_config
            else:
                spec_config = _spec_opts_or_config

        # Require exactly one of the typed parameters to be set
        if spec_opts is not None:
            assert spec_config is None, "Cannot provide both spec_opts and spec_config"
            final_config = HookspecConfiguration(**spec_opts)
        elif spec_config is not None:
            final_config = spec_config
        else:
            raise TypeError("Must provide either spec_opts or spec_config")

        if final_config.historic:
            raise ValueError(
                f"HookCaller cannot handle historic hooks. "
                f"Use HistoricHookCaller for {self.name!r}"
            )
        self.spec = HookSpec(specmodule_or_class, self.name, final_config)

    def is_historic(self) -> bool:
        """Whether this caller is :ref:`historic <historic>`."""
        return False  # HookCaller is never historic

    def _remove_plugin(self, plugin: _Plugin) -> None:
        # Try to remove from normal hookimpls first
        for i, normal_method in enumerate(self._normal_hookimpls):
            if normal_method.plugin == plugin:
                del self._normal_hookimpls[i]
                return
        # Then try wrapper hookimpls
        for i, wrapper_method in enumerate(self._wrapper_hookimpls):
            if wrapper_method.plugin == plugin:
                del self._wrapper_hookimpls[i]
                return
        raise ValueError(f"plugin {plugin!r} not found")

    def get_hookimpls(self) -> list[HookImpl]:
        """Get all registered hook implementations for this hook."""
        # Combine normal hooks and wrapper hooks in the correct order
        # Normal hooks come first, then wrapper hooks (execution order is reversed)
        return cast(list[HookImpl], [*self._normal_hookimpls, *self._wrapper_hookimpls])

    def _add_hookimpl(self, hookimpl: HookImpl | WrapperImpl) -> None:
        """Add an implementation to the callback chain."""
        # Choose the appropriate list based on type
        if isinstance(hookimpl, WrapperImpl):
            _insert_hookimpl_into_list(hookimpl, self._wrapper_hookimpls)
        else:
            _insert_hookimpl_into_list(hookimpl, self._normal_hookimpls)

    def __repr__(self) -> str:
        return f"<NormalHookCaller {self.name!r}>"

    def __call__(self, **kwargs: object) -> Any:
        """Call the hook.

        Only accepts keyword arguments, which should match the hook
        specification.

        Returns the result(s) of calling all registered plugins, see
        :ref:`calling`.
        """
        if self.spec:
            self.spec.verify_all_args_are_provided(kwargs)
        firstresult = self.spec.config.firstresult if self.spec else False
        # Copy because plugins may register other plugins during iteration (#438).
        return self._hookexec(
            self.name,
            self._normal_hookimpls.copy(),
            self._wrapper_hookimpls.copy(),
            kwargs,
            firstresult,
        )

    def call_historic(
        self,
        result_callback: Callable[[Any], None] | None = None,
        kwargs: Mapping[str, object] | None = None,
    ) -> None:
        """Call the hook with given ``kwargs`` for all registered plugins and
        for all plugins which will be registered afterwards, see
        :ref:`historic`.

        This method should not be called on non-historic hooks.
        """
        raise AssertionError(
            f"Hook {self.name!r} is not historic - cannot call call_historic"
        )

    def call_extra(
        self, methods: Sequence[Callable[..., object]], kwargs: Mapping[str, object]
    ) -> Any:
        """Call the hook with some additional temporarily participating
        methods using the specified ``kwargs`` as call parameters, see
        :ref:`call_extra`."""
        if self.spec:
            self.spec.verify_all_args_are_provided(kwargs)
        config = HookimplConfiguration()
        # Start with copies of our separate lists
        normal_hookimpls = self._normal_hookimpls.copy()

        for method in methods:
            hookimpl = config.create_hookimpl(None, "<temp>", method)
            # call_extra only supports normal implementations
            assert isinstance(hookimpl, HookImpl)
            # Add temporary methods to the normal hookimpls list
            _insert_hookimpl_into_list(hookimpl, normal_hookimpls)

        firstresult = self.spec.config.firstresult if self.spec else False
        return self._hookexec(
            self.name,
            normal_hookimpls,
            self._wrapper_hookimpls.copy(),
            kwargs,
            firstresult,
        )


# Historical name (pluggy<=1.2), kept for backward compatibility.
_HookCaller = NormalHookCaller


class SubsetHookCaller:
    """A proxy to another HookCaller which manages calls to all registered
    plugins except the ones from remove_plugins."""

    __slots__ = (
        "_orig",
        "_remove_plugins",
    )
    _orig: NormalHookCaller | HistoricHookCaller
    _remove_plugins: Set[_Plugin]

    def __init__(
        self,
        orig: NormalHookCaller | HistoricHookCaller,
        remove_plugins: Set[_Plugin],
    ) -> None:
        self._orig = orig
        self._remove_plugins = remove_plugins

    @property
    def name(self) -> str:
        return self._orig.name

    @property
    def spec(self) -> HookSpec | None:
        return self._orig.spec

    def has_spec(self) -> bool:
        return self._orig.has_spec()

    def is_historic(self) -> bool:
        return self._orig.is_historic()

    def _get_filtered(self, hooks: Sequence[_T_HookImpl]) -> list[_T_HookImpl]:
        """Filter out hook implementations from removed plugins."""
        return [impl for impl in hooks if impl.plugin not in self._remove_plugins]

    def get_hookimpls(self) -> list[HookImpl]:
        """Get filtered hook implementations for this hook."""
        return self._get_filtered(self._orig.get_hookimpls())

    def set_specification(
        self,
        specmodule_or_class: _Namespace,
        _spec_opts_or_config: HookspecOpts | HookspecConfiguration | None = None,
        *,
        spec_opts: HookspecOpts | None = None,
        spec_config: HookspecConfiguration | None = None,
    ) -> None:
        """SubsetHookCaller cannot set specifications - they are read-only proxies."""
        raise RuntimeError(
            f"Cannot set specification on SubsetHookCaller {self.name!r} - "
            "it is a read-only proxy to another hook caller"
        )

    def __call__(self, **kwargs: object) -> Any:
        """Call the hook with filtered implementations."""
        if self.is_historic():
            raise RuntimeError(
                "Cannot directly call a historic hook - use call_historic instead."
            )
        assert isinstance(self._orig, NormalHookCaller)
        if self.spec:
            self.spec.verify_all_args_are_provided(kwargs)
        firstresult = self.spec.config.firstresult if self.spec else False
        hookexec = getattr(self._orig, "_hookexec")

        normal_impls = self._get_filtered(self._orig._normal_hookimpls)
        wrapper_impls = self._get_filtered(self._orig._wrapper_hookimpls)
        return hookexec(self.name, normal_impls, wrapper_impls, kwargs, firstresult)

    def call_historic(
        self,
        result_callback: Callable[[Any], None] | None = None,
        kwargs: Mapping[str, object] | None = None,
    ) -> None:
        """Call the hook with given ``kwargs`` for all registered plugins and
        for all plugins which will be registered afterwards, see
        :ref:`historic`.
        """
        if not self.is_historic():
            raise AssertionError(
                f"Hook {self.name!r} is not historic - cannot call call_historic"
            )
        assert isinstance(self._orig, HistoricHookCaller)
        # For subset hook callers, we need to manually handle the history and execution
        kwargs = kwargs or {}
        if self.spec:
            self.spec.verify_all_args_are_provided(kwargs)

        self._orig._call_history.append((kwargs, result_callback))

        # Execute with filtered hookimpls (historic hooks don't support wrappers)
        hookexec = getattr(self._orig, "_hookexec")

        normal_impls = self._get_filtered(self._orig._hookimpls)
        wrapper_impls: list[WrapperImpl] = []

        # Historic hooks should have empty wrapper list
        assert not wrapper_impls, "Historic hooks don't support wrappers"
        empty_wrappers = cast(list[WrapperImpl], [])
        res = hookexec(self.name, normal_impls, empty_wrappers, kwargs, False)
        if result_callback is None:
            return
        if isinstance(res, list):
            for x in res:
                result_callback(x)

    def call_extra(
        self, methods: Sequence[Callable[..., object]], kwargs: Mapping[str, object]
    ) -> Any:
        """Call the hook with some additional temporarily participating methods."""
        if self.is_historic():
            raise RuntimeError(
                "Cannot call call_extra on a historic hook - use call_historic instead."
            )
        assert isinstance(self._orig, NormalHookCaller)
        if self.spec:
            self.spec.verify_all_args_are_provided(kwargs)
        config = HookimplConfiguration()
        normal_impls = self._get_filtered(self._orig._normal_hookimpls)
        wrapper_impls = self._get_filtered(self._orig._wrapper_hookimpls)

        # Add extra methods to normal implementations list
        for method in methods:
            hookimpl = config.create_hookimpl(None, "<temp>", method)
            # call_extra only supports normal implementations
            assert isinstance(hookimpl, HookImpl)
            # Use the same insertion logic as NormalHookCaller.call_extra
            _insert_hookimpl_into_list(hookimpl, normal_impls)

        firstresult = self.spec.config.firstresult if self.spec else False
        hookexec = getattr(self._orig, "_hookexec")
        return hookexec(self.name, normal_impls, wrapper_impls, kwargs, firstresult)

    def __repr__(self) -> str:
        return f"<SubsetHookCaller {self.name!r}>"


# Historical name (pluggy<=1.2), kept for backward compatibility.
_SubsetHookCaller = SubsetHookCaller


class HookImpl:
    """Base class for hook implementations in a :class:`HookCaller`."""

    __slots__ = (
        "function",
        "argnames",
        "kwargnames",
        "plugin",
        "plugin_name",
        "wrapper",
        "hookwrapper",
        "optionalhook",
        "tryfirst",
        "trylast",
        "hookimpl_config",
    )

    function: Final[_HookImplFunction[object]]
    argnames: Final[tuple[str, ...]]
    kwargnames: Final[tuple[str, ...]]
    plugin: Final[_Plugin]
    plugin_name: Final[str]
    wrapper: Final[bool]
    hookwrapper: Final[bool]
    optionalhook: Final[bool]
    tryfirst: Final[bool]
    trylast: Final[bool]
    hookimpl_config: Final[HookimplConfiguration]

    def __init__(
        self,
        plugin: _Plugin,
        plugin_name: str,
        function: _HookImplFunction[object],
        hook_impl_config: HookimplConfiguration,
    ) -> None:
        """:meta private:"""
        #: The hook implementation function.
        self.function = function
        argnames, kwargnames = varnames(self.function)
        #: The positional parameter names of ``function```.
        self.argnames = argnames
        #: The keyword parameter names of ``function```.
        self.kwargnames = kwargnames
        #: The plugin which defined this hook implementation.
        self.plugin = plugin
        #: The :class:`HookimplConfiguration` used to configure this hook
        #: implementation.
        self.hookimpl_config = hook_impl_config
        #: The name of the plugin which defined this hook implementation.
        self.plugin_name = plugin_name
        #: Whether the hook implementation is a :ref:`wrapper <hookwrapper>`.
        self.wrapper = hook_impl_config.wrapper
        #: Whether the hook implementation is an :ref:`old-style wrapper
        #: <old_style_hookwrappers>`.
        self.hookwrapper = hook_impl_config.hookwrapper
        #: Whether validation against a hook specification is :ref:`optional
        #: <optionalhook>`.
        self.optionalhook = hook_impl_config.optionalhook
        #: Whether to try to order this hook implementation :ref:`first
        #: <callorder>`.
        self.tryfirst = hook_impl_config.tryfirst
        #: Whether to try to order this hook implementation :ref:`last
        #: <callorder>`.
        self.trylast = hook_impl_config.trylast

    def _get_call_args(self, caller_kwargs: Mapping[str, object]) -> list[object]:
        """Extract arguments for calling this hook implementation.

        Args:
            caller_kwargs: Keyword arguments passed to the hook call

        Returns:
            List of arguments in the order expected by the hook implementation

        Raises:
            HookCallError: If required arguments are missing
        """
        try:
            return [caller_kwargs[argname] for argname in self.argnames]
        except KeyError as e:
            # Find the first missing argument for a clearer error message
            for argname in self.argnames:  # pragma: no cover
                if argname not in caller_kwargs:
                    raise HookCallError(
                        f"hook call must provide argument {argname!r}"
                    ) from e
            # This should never be reached but keep the original exception just in case
            raise  # pragma: no cover

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"plugin_name={self.plugin_name!r}, plugin={self.plugin!r}>"
        )


@final
class NormalImpl(HookImpl):
    """A normal hook implementation in a :class:`HookCaller`."""

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
                "HookImpl cannot be used for wrapper implementations. "
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
                "Use HookImpl for normal implementations."
            )
        super().__init__(plugin, plugin_name, function, hook_impl_config)

    def setup_and_get_completion_hook(
        self, hook_name: str, caller_kwargs: Mapping[str, object]
    ) -> CompletionHook:
        """Set up wrapper and return a completion hook for teardown processing.

        This method provides a streamlined way to handle wrapper setup and teardown.
        Both old-style hookwrappers and new-style wrappers are handled uniformly
        by converting old-style wrappers to the new protocol using
        run_old_style_hookwrapper.

        Args:
            hook_name: Name of the hook being called
            caller_kwargs: Keyword arguments passed to the hook call

        Returns:
            A completion hook function that handles the teardown process
        """
        args = self._get_call_args(caller_kwargs)

        # Use run_old_style_hookwrapper for old-style, direct generator for new-style
        if self.hookwrapper:
            from ._callers import run_old_style_hookwrapper

            wrapper_gen = run_old_style_hookwrapper(self, hook_name, args)
        else:
            # New-style wrapper handling
            res = self.function(*args)
            wrapper_gen = cast(Generator[None, object, object], res)

        # Start the wrapper generator - this is where "did not yield" is checked
        try:
            next(wrapper_gen)  # first yield
        except StopIteration:
            from ._callers import _raise_wrapfail

            _raise_wrapfail(wrapper_gen, "did not yield")

        def completion_hook(
            result: object | list[object] | None, exception: BaseException | None
        ) -> tuple[object | list[object] | None, BaseException | None]:
            """Unified completion hook for both old-style and new-style wrappers."""
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
                from ._callers import _raise_wrapfail

                _raise_wrapfail(wrapper_gen, "has second yield")
            except StopIteration as si:
                return si.value, None
            except BaseException as e:
                return result, e

        return completion_hook
