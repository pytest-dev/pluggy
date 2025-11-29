"""
Internal hook annotation, representation and calling machinery.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from collections.abc import Callable
from collections.abc import Generator
from collections.abc import Mapping
from collections.abc import Sequence
from collections.abc import Set
import inspect
import sys
from types import ModuleType
from typing import Any
from typing import Final
from typing import final
from typing import overload
from typing import Protocol
from typing import runtime_checkable
from typing import TYPE_CHECKING
from typing import TypeAlias
from typing import TypedDict
from typing import TypeVar
import warnings

from ._result import Result


_T = TypeVar("_T")
_F = TypeVar("_F", bound=Callable[..., object])

_Namespace: TypeAlias = ModuleType | type
_Plugin: TypeAlias = object
# Teardown function: takes (result, exception), returns (result, exception)
Teardown: TypeAlias = Callable[
    [object, BaseException | None], tuple[object, BaseException | None]
]
# Hook execution function signature:
# (name, normal_impls, wrapper_impls, kwargs, firstresult)
_HookExec: TypeAlias = Callable[
    [
        str,
        Sequence["_NormalHookImplementation"],
        Sequence["_WrapperHookImplementation"],
        Mapping[str, object],
        bool,
    ],
    object | list[object],
]
_HookImplFunction: TypeAlias = Callable[..., _T | Generator[None, Result[_T], None]]


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
class HookspecMarker:
    """Decorator for marking functions as hook specifications.

    Instantiate it with a project_name to get a decorator.
    Calling :meth:`PluginManager.add_hookspecs` later will discover all marked
    functions if the :class:`PluginManager` uses the same project name.
    """

    __slots__ = ("project_name",)

    def __init__(self, project_name: str) -> None:
        self.project_name: Final = project_name

    @overload
    def __call__(
        self,
        function: _F,
        firstresult: bool = False,
        historic: bool = False,
        warn_on_impl: Warning | None = None,
        warn_on_impl_args: Mapping[str, Warning] | None = None,
    ) -> _F: ...

    @overload  # noqa: F811
    def __call__(  # noqa: F811
        self,
        function: None = ...,
        firstresult: bool = ...,
        historic: bool = ...,
        warn_on_impl: Warning | None = ...,
        warn_on_impl_args: Mapping[str, Warning] | None = ...,
    ) -> Callable[[_F], _F]: ...

    def __call__(  # noqa: F811
        self,
        function: _F | None = None,
        firstresult: bool = False,
        historic: bool = False,
        warn_on_impl: Warning | None = None,
        warn_on_impl_args: Mapping[str, Warning] | None = None,
    ) -> _F | Callable[[_F], _F]:
        """If passed a function, directly sets attributes on the function
        which will make it discoverable to :meth:`PluginManager.add_hookspecs`.

        If passed no function, returns a decorator which can be applied to a
        function later using the attributes supplied.

        :param firstresult:
            If ``True``, the 1:N hook call (N being the number of registered
            hook implementation functions) will stop at I<=N when the I'th
            function returns a non-``None`` result. See :ref:`firstresult`.

        :param historic:
            If ``True``, every call to the hook will be memorized and replayed
            on plugins registered after the call was made. See :ref:`historic`.

        :param warn_on_impl:
            If given, every implementation of this hook will trigger the given
            warning. See :ref:`warn_on_impl`.

        :param warn_on_impl_args:
            If given, every implementation of this hook which requests one of
            the arguments in the dict will trigger the corresponding warning.
            See :ref:`warn_on_impl`.

            .. versionadded:: 1.5
        """

        def setattr_hookspec_opts(func: _F) -> _F:
            if historic and firstresult:
                raise ValueError("cannot have a historic firstresult hook")
            opts: HookspecOpts = {
                "firstresult": firstresult,
                "historic": historic,
                "warn_on_impl": warn_on_impl,
                "warn_on_impl_args": warn_on_impl_args,
            }
            setattr(func, self.project_name + "_spec", opts)
            return func

        if function is not None:
            return setattr_hookspec_opts(function)
        else:
            return setattr_hookspec_opts


@final
class HookimplMarker:
    """Decorator for marking functions as hook implementations.

    Instantiate it with a ``project_name`` to get a decorator.
    Calling :meth:`PluginManager.register` later will discover all marked
    functions if the :class:`PluginManager` uses the same project name.
    """

    __slots__ = ("project_name",)

    def __init__(self, project_name: str) -> None:
        self.project_name: Final = project_name

    @overload
    def __call__(
        self,
        function: _F,
        hookwrapper: bool = ...,
        optionalhook: bool = ...,
        tryfirst: bool = ...,
        trylast: bool = ...,
        specname: str | None = ...,
        wrapper: bool = ...,
    ) -> _F: ...

    @overload  # noqa: F811
    def __call__(  # noqa: F811
        self,
        function: None = ...,
        hookwrapper: bool = ...,
        optionalhook: bool = ...,
        tryfirst: bool = ...,
        trylast: bool = ...,
        specname: str | None = ...,
        wrapper: bool = ...,
    ) -> Callable[[_F], _F]: ...

    def __call__(  # noqa: F811
        self,
        function: _F | None = None,
        hookwrapper: bool = False,
        optionalhook: bool = False,
        tryfirst: bool = False,
        trylast: bool = False,
        specname: str | None = None,
        wrapper: bool = False,
    ) -> _F | Callable[[_F], _F]:
        """If passed a function, directly sets attributes on the function
        which will make it discoverable to :meth:`PluginManager.register`.

        If passed no function, returns a decorator which can be applied to a
        function later using the attributes supplied.

        :param optionalhook:
            If ``True``, a missing matching hook specification will not result
            in an error (by default it is an error if no matching spec is
            found). See :ref:`optionalhook`.

        :param tryfirst:
            If ``True``, this hook implementation will run as early as possible
            in the chain of N hook implementations for a specification. See
            :ref:`callorder`.

        :param trylast:
            If ``True``, this hook implementation will run as late as possible
            in the chain of N hook implementations for a specification. See
            :ref:`callorder`.

        :param wrapper:
            If ``True`` ("new-style hook wrapper"), the hook implementation
            needs to execute exactly one ``yield``. The code before the
            ``yield`` is run early before any non-hook-wrapper function is run.
            The code after the ``yield`` is run after all non-hook-wrapper
            functions have run. The ``yield`` receives the result value of the
            inner calls, or raises the exception of inner calls (including
            earlier hook wrapper calls). The return value of the function
            becomes the return value of the hook, and a raised exception becomes
            the exception of the hook. See :ref:`hookwrapper`.

        :param hookwrapper:
            If ``True`` ("old-style hook wrapper"), the hook implementation
            needs to execute exactly one ``yield``. The code before the
            ``yield`` is run early before any non-hook-wrapper function is run.
            The code after the ``yield`` is run after all non-hook-wrapper
            function have run  The ``yield`` receives a :class:`Result` object
            representing the exception or result outcome of the inner calls
            (including earlier hook wrapper calls). This option is mutually
            exclusive with ``wrapper``. See :ref:`old_style_hookwrapper`.

        :param specname:
            If provided, the given name will be used instead of the function
            name when matching this hook implementation to a hook specification
            during registration. See :ref:`specname`.

        .. versionadded:: 1.2.0
            The ``wrapper`` parameter.
        """

        def setattr_hookimpl_opts(func: _F) -> _F:
            opts: HookimplOpts = {
                "wrapper": wrapper,
                "hookwrapper": hookwrapper,
                "optionalhook": optionalhook,
                "tryfirst": tryfirst,
                "trylast": trylast,
                "specname": specname,
            }
            setattr(func, self.project_name + "_impl", opts)
            return func

        if function is None:
            return setattr_hookimpl_opts
        else:
            return setattr_hookimpl_opts(function)


def normalize_hookimpl_opts(opts: HookimplOpts) -> None:
    opts.setdefault("tryfirst", False)
    opts.setdefault("trylast", False)
    opts.setdefault("wrapper", False)
    opts.setdefault("hookwrapper", False)
    opts.setdefault("optionalhook", False)
    opts.setdefault("specname", None)


_PYPY = hasattr(sys, "pypy_version_info")


def varnames(func: object) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return tuple of positional and keywrord argument names for a function,
    method, class or callable.

    In case of a class, its ``__init__`` method is considered.
    For methods the ``self`` parameter is not included.
    """
    if inspect.isclass(func):
        try:
            func = func.__init__
        except AttributeError:  # pragma: no cover - pypy special case
            return (), ()
    elif not inspect.isroutine(func):  # callable object?
        try:
            func = getattr(func, "__call__", func)
        except Exception:  # pragma: no cover - pypy special case
            return (), ()

    try:
        # func MUST be a function or method here or we won't parse any args.
        sig = inspect.signature(
            func.__func__ if inspect.ismethod(func) else func  # type:ignore[arg-type]
        )
    except TypeError:  # pragma: no cover
        return (), ()

    _valid_param_kinds = (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )
    _valid_params = {
        name: param
        for name, param in sig.parameters.items()
        if param.kind in _valid_param_kinds
    }
    args = tuple(_valid_params)
    defaults = (
        tuple(
            param.default
            for param in _valid_params.values()
            if param.default is not param.empty
        )
        or None
    )

    if defaults:
        index = -len(defaults)
        args, kwargs = args[:index], tuple(args[index:])
    else:
        kwargs = ()

    # strip any implicit instance arg
    # pypy3 uses "obj" instead of "self" for default dunder methods
    if not _PYPY:
        implicit_names: tuple[str, ...] = ("self",)
    else:  # pragma: no cover
        implicit_names = ("self", "obj")
    if args:
        qualname: str = getattr(func, "__qualname__", "")
        if inspect.ismethod(func) or ("." in qualname and args[0] in implicit_names):
            args = args[1:]

    return args, kwargs


@final
class HookRelay:
    """Hook holder object for performing 1:N hook calls where N is the number
    of registered plugins."""

    __slots__ = ("__dict__",)

    def __init__(self) -> None:
        """:meta private:"""

    if TYPE_CHECKING:
        # Return Any since the actual hook type varies (normal, firstresult, historic)
        def __getattr__(self, name: str) -> Any: ...


# Historical name (pluggy<=1.2), kept for backward compatibility.
_HookRelay = HookRelay


_CallHistory: TypeAlias = list[
    tuple[Mapping[str, object], Callable[[Any], None] | None]
]


@runtime_checkable
class HookCallerProtocol(Protocol):
    """Public protocol for hook callers.

    This is the stable public interface that API users should depend on
    for type hints. The concrete implementation classes are internal.
    """

    @property
    def name(self) -> str: ...

    @property
    def spec(self) -> HookSpec | None: ...

    def has_spec(self) -> bool: ...

    def is_historic(self) -> bool: ...

    def __call__(self, **kwargs: object) -> Any: ...

    def call_extra(
        self, methods: Sequence[Callable[..., object]], kwargs: Mapping[str, object]
    ) -> Any: ...

    def call_historic(
        self,
        result_callback: Callable[[Any], None] | None = ...,
        kwargs: Mapping[str, object] | None = ...,
    ) -> None: ...


class _HookCallerBase(ABC):
    """Base class for all hook callers (internal).

    Use :class:`HookCallerProtocol` for type hints in public APIs.
    """

    __slots__ = ("name", "_hookexec", "_normal_impls", "_wrapper_impls")

    def __init__(self, name: str, hook_execute: _HookExec) -> None:
        self.name: Final = name
        self._hookexec: Final = hook_execute
        # Separate lists for normal and wrapper implementations.
        # Each list ordered: [trylast..., normal..., tryfirst...]
        self._normal_impls: list[_NormalHookImplementation] = []
        self._wrapper_impls: list[_WrapperHookImplementation] = []

    def get_hookimpls(self) -> list[_HookImplementation]:
        """Get all registered hook implementations for this hook.

        .. deprecated::
            Access ``_normal_impls`` and ``_wrapper_impls`` directly instead.
        """
        return list(self._normal_impls) + list(self._wrapper_impls)

    def _insert_by_priority(
        self,
        impl_list: list[_HookImplementation],
        hookimpl: _HookImplementation,
    ) -> None:
        """Insert hookimpl into list maintaining priority order."""
        if hookimpl.trylast:
            impl_list.insert(0, hookimpl)
        elif hookimpl.tryfirst:
            impl_list.append(hookimpl)
        else:
            # Find last non-tryfirst impl
            i = len(impl_list)
            while i > 0 and impl_list[i - 1].tryfirst:
                i -= 1
            impl_list.insert(i, hookimpl)

    def _add_hookimpl(self, hookimpl: _HookImplementation) -> None:
        """Add to appropriate list based on wrapper type."""
        if hookimpl.is_wrapper:
            self._insert_by_priority(
                self._wrapper_impls,  # type: ignore[arg-type]
                hookimpl,
            )
        else:
            self._insert_by_priority(
                self._normal_impls,  # type: ignore[arg-type]
                hookimpl,
            )

    def _remove_plugin(self, plugin: _Plugin) -> None:
        """Remove all hookimpls for a plugin."""
        for i, impl in enumerate(self._normal_impls):
            if impl.plugin == plugin:
                del self._normal_impls[i]
                return
        for i, wrapper in enumerate(self._wrapper_impls):
            if wrapper.plugin == plugin:
                del self._wrapper_impls[i]
                return
        raise ValueError(f"plugin {plugin!r} not found")

    @abstractmethod
    def has_spec(self) -> bool: ...

    @abstractmethod
    def is_historic(self) -> bool: ...

    @property
    @abstractmethod
    def spec(self) -> HookSpec | None: ...

    def call_extra(
        self, methods: Sequence[Callable[..., object]], kwargs: Mapping[str, object]
    ) -> Any:
        """Call with additional temporary methods.

        Override in subclasses that support this operation.
        """
        raise TypeError(f"{type(self).__name__!r} does not support call_extra")

    def call_historic(
        self,
        result_callback: Callable[[Any], None] | None = None,
        kwargs: Mapping[str, object] | None = None,
    ) -> None:
        """Call with historic registration.

        Override in subclasses that support this operation.
        """
        raise TypeError(f"{type(self).__name__!r} does not support call_historic")

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name!r}>"


@final
class _UnspeccedHookCaller(_HookCallerBase):
    """Hook without specification - replaced when spec is added."""

    __slots__ = ()

    @property
    def spec(self) -> None:
        return None

    def has_spec(self) -> bool:
        return False

    def is_historic(self) -> bool:
        return False

    def _verify_all_args_are_provided(self, _kwargs: Mapping[str, object]) -> None:
        # No spec, no verification needed
        pass

    def __call__(self, **kwargs: object) -> list[object]:
        # Copy because plugins may register other plugins during iteration (#438).
        return self._hookexec(  # type: ignore[return-value]
            self.name,
            self._normal_impls.copy(),
            self._wrapper_impls.copy(),
            kwargs,
            False,
        )


class _SpecifiedHookCaller(_HookCallerBase, ABC):
    """Base for hooks with a specification."""

    __slots__ = ("_spec",)

    def __init__(
        self,
        name: str,
        hook_execute: _HookExec,
        specmodule_or_class: _Namespace,
        spec_opts: HookspecOpts,
    ) -> None:
        super().__init__(name, hook_execute)
        self._spec: Final = HookSpec(specmodule_or_class, name, spec_opts)

    @property
    def spec(self) -> HookSpec:
        return self._spec

    def has_spec(self) -> bool:
        return True

    @abstractmethod
    def __call__(self, **kwargs: object) -> Any: ...

    def _verify_all_args_are_provided(self, kwargs: Mapping[str, object]) -> None:
        # This is written to avoid expensive operations when not needed.
        for argname in self._spec.argnames:
            if argname not in kwargs:
                notincall = ", ".join(
                    repr(argname)
                    for argname in self._spec.argnames
                    if argname not in kwargs.keys()
                )
                warnings.warn(
                    f"Argument(s) {notincall} which are declared in the hookspec "
                    "cannot be found in this hook call",
                    stacklevel=3,
                )
                break


@final
class _NormalHookCaller(_SpecifiedHookCaller):
    """Returns list of all non-None results."""

    __slots__ = ()

    def is_historic(self) -> bool:
        return False

    def __call__(self, **kwargs: object) -> list[object]:
        self._verify_all_args_are_provided(kwargs)
        # Copy because plugins may register other plugins during iteration (#438).
        return self._hookexec(  # type: ignore[return-value]
            self.name,
            self._normal_impls.copy(),
            self._wrapper_impls.copy(),
            kwargs,
            False,
        )

    def call_extra(
        self, methods: Sequence[Callable[..., object]], kwargs: Mapping[str, object]
    ) -> list[object]:
        """Call with additional temporary methods."""
        self._verify_all_args_are_provided(kwargs)
        opts: HookimplOpts = {
            "wrapper": False,
            "hookwrapper": False,
            "optionalhook": False,
            "trylast": False,
            "tryfirst": False,
            "specname": None,
        }
        # Build list of normal impls with extras inserted
        normal_impls: list[_NormalHookImplementation] = list(self._normal_impls)
        for method in methods:
            hookimpl = _NormalHookImplementation(None, "<temp>", method, opts)
            # Find last non-tryfirst method.
            i = len(normal_impls) - 1
            while i >= 0 and normal_impls[i].tryfirst:
                i -= 1
            normal_impls.insert(i + 1, hookimpl)
        return self._hookexec(  # type: ignore[return-value]
            self.name, normal_impls, list(self._wrapper_impls), kwargs, False
        )


@final
class _FirstResultHookCaller(_SpecifiedHookCaller):
    """Returns first non-None result."""

    __slots__ = ()

    def is_historic(self) -> bool:
        return False

    def __call__(self, **kwargs: object) -> object | None:
        self._verify_all_args_are_provided(kwargs)
        # Copy because plugins may register other plugins during iteration (#438).
        return self._hookexec(
            self.name,
            self._normal_impls.copy(),
            self._wrapper_impls.copy(),
            kwargs,
            True,
        )

    def call_extra(
        self, methods: Sequence[Callable[..., object]], kwargs: Mapping[str, object]
    ) -> object | None:
        """Call with additional temporary methods."""
        self._verify_all_args_are_provided(kwargs)
        opts: HookimplOpts = {
            "wrapper": False,
            "hookwrapper": False,
            "optionalhook": False,
            "trylast": False,
            "tryfirst": False,
            "specname": None,
        }
        # Build list of normal impls with extras inserted
        normal_impls: list[_NormalHookImplementation] = list(self._normal_impls)
        for method in methods:
            hookimpl = _NormalHookImplementation(None, "<temp>", method, opts)
            # Find last non-tryfirst method.
            i = len(normal_impls) - 1
            while i >= 0 and normal_impls[i].tryfirst:
                i -= 1
            normal_impls.insert(i + 1, hookimpl)
        return self._hookexec(
            self.name, normal_impls, list(self._wrapper_impls), kwargs, True
        )


@final
class _HistoricHookCaller(_SpecifiedHookCaller):
    """Memorizes calls and replays to new registrations."""

    __slots__ = ("_call_history",)

    def __init__(
        self,
        name: str,
        hook_execute: _HookExec,
        specmodule_or_class: _Namespace,
        spec_opts: HookspecOpts,
    ) -> None:
        super().__init__(name, hook_execute, specmodule_or_class, spec_opts)
        self._call_history: _CallHistory = []

    def is_historic(self) -> bool:
        return True

    def _add_hookimpl(self, hookimpl: _HookImplementation) -> None:
        if hookimpl.is_wrapper:
            from ._manager import PluginValidationError

            raise PluginValidationError(
                hookimpl.plugin,
                f"Plugin {hookimpl.plugin_name!r}\nhook {self.name!r}\n"
                "historic hooks cannot have wrappers",
            )
        super()._add_hookimpl(hookimpl)

    def __call__(self, **_kwargs: object) -> Any:
        raise TypeError(
            "Cannot directly call a historic hook - use call_historic instead."
        )

    def call_historic(
        self,
        result_callback: Callable[[Any], None] | None = None,
        kwargs: Mapping[str, object] | None = None,
    ) -> None:
        """Call the hook with given ``kwargs`` for all registered plugins and
        for all plugins which will be registered afterwards.

        :param result_callback:
            If provided, will be called for each non-``None`` result obtained
            from a hook implementation.
        """
        kwargs = kwargs or {}
        self._verify_all_args_are_provided(kwargs)
        self._call_history.append((kwargs, result_callback))
        # Historizing hooks don't return results.
        # Historic hooks don't have wrappers (enforced in _add_hookimpl).
        # Copy because plugins may register other plugins during iteration (#438).
        res = self._hookexec(self.name, self._normal_impls.copy(), [], kwargs, False)
        if result_callback is None:
            return
        if isinstance(res, list):
            for x in res:
                result_callback(x)

    def _maybe_apply_history(self, method: _NormalHookImplementation) -> None:
        """Apply call history to a new hookimpl if it is marked as historic."""
        for kwargs, result_callback in self._call_history:
            res = self._hookexec(self.name, [method], [], kwargs, False)
            if res and result_callback is not None:
                assert isinstance(res, list)
                result_callback(res[0])


def _create_hook_caller(
    name: str,
    hook_execute: _HookExec,
    specmodule_or_class: _Namespace | None = None,
    spec_opts: HookspecOpts | None = None,
) -> _HookCallerBase:
    """Factory returning appropriate HookCaller type (internal)."""
    if specmodule_or_class is None:
        return _UnspeccedHookCaller(name, hook_execute)

    assert spec_opts is not None
    if spec_opts.get("historic"):
        return _HistoricHookCaller(name, hook_execute, specmodule_or_class, spec_opts)
    elif spec_opts.get("firstresult"):
        return _FirstResultHookCaller(
            name, hook_execute, specmodule_or_class, spec_opts
        )
    else:
        return _NormalHookCaller(name, hook_execute, specmodule_or_class, spec_opts)


class _SubsetHookCaller:
    """A proxy to another HookCaller which manages calls to all registered
    plugins except the ones from remove_plugins."""

    __slots__ = ("_orig", "_remove_plugins")

    def __init__(
        self, orig: _SpecifiedHookCaller, remove_plugins: Set[_Plugin]
    ) -> None:
        self._orig = orig
        self._remove_plugins = remove_plugins

    @property
    def name(self) -> str:
        return self._orig.name

    @property
    def spec(self) -> HookSpec:
        return self._orig.spec

    @property
    def _normal_impls(self) -> list[_NormalHookImplementation]:
        return [
            impl
            for impl in self._orig._normal_impls
            if impl.plugin not in self._remove_plugins
        ]

    @property
    def _wrapper_impls(self) -> list[_WrapperHookImplementation]:
        return [
            impl
            for impl in self._orig._wrapper_impls
            if impl.plugin not in self._remove_plugins
        ]

    def get_hookimpls(self) -> list[_HookImplementation]:
        """Get all registered hook implementations for this hook."""
        return list(self._normal_impls) + list(self._wrapper_impls)

    def has_spec(self) -> bool:
        return True

    def is_historic(self) -> bool:
        return self._orig.is_historic()

    @property
    def _call_history(self) -> _CallHistory | None:
        if isinstance(self._orig, _HistoricHookCaller):
            return self._orig._call_history
        return None

    def __call__(self, **kwargs: object) -> Any:
        """Call the hook with filtered implementations."""
        self._orig._verify_all_args_are_provided(kwargs)
        firstresult = isinstance(self._orig, _FirstResultHookCaller)
        return self._orig._hookexec(
            self.name,
            self._normal_impls.copy(),
            self._wrapper_impls.copy(),
            kwargs,
            firstresult,
        )

    def call_historic(
        self,
        result_callback: Callable[[Any], None] | None = None,
        kwargs: Mapping[str, object] | None = None,
    ) -> None:
        """Call a historic hook with given kwargs for all filtered plugins.

        Also registers the call in the original hook's history so new plugins
        will receive the call (subject to the original's filtering, not this subset's).
        """
        if not isinstance(self._orig, _HistoricHookCaller):
            raise TypeError("call_historic is only valid for historic hooks")
        kwargs = kwargs or {}
        self._orig._verify_all_args_are_provided(kwargs)
        # Store in original's history - new plugins get the call via the original
        self._orig._call_history.append((kwargs, result_callback))
        # Call with filtered implementations
        res = self._orig._hookexec(
            self.name, self._normal_impls.copy(), [], kwargs, False
        )
        if result_callback is None:
            return
        if isinstance(res, list):
            for x in res:
                result_callback(x)

    def __repr__(self) -> str:
        return f"<_SubsetHookCaller {self.name!r}>"


# Backward compatibility alias
HookCaller = _NormalHookCaller
_HookCaller = _NormalHookCaller


@runtime_checkable
class HookImplementationProtocol(Protocol):
    """Public protocol for hook implementations.

    This is the stable public interface that API users should depend on
    for type hints. The concrete implementation classes are internal.
    """

    @property
    def function(self) -> Callable[..., object]: ...

    @property
    def argnames(self) -> tuple[str, ...]: ...

    @property
    def kwargnames(self) -> tuple[str, ...]: ...

    @property
    def plugin(self) -> _Plugin: ...

    @property
    def plugin_name(self) -> str: ...

    @property
    def optionalhook(self) -> bool: ...

    @property
    def tryfirst(self) -> bool: ...

    @property
    def trylast(self) -> bool: ...


class _HookImplementation(ABC):
    """Base class for all hook implementations (internal).

    Use :class:`HookImplementationProtocol` for type hints in public APIs.
    """

    __slots__ = (
        "function",
        "argnames",
        "kwargnames",
        "plugin",
        "plugin_name",
        "optionalhook",
        "tryfirst",
        "trylast",
    )

    def __init__(
        self,
        plugin: _Plugin,
        plugin_name: str,
        function: _HookImplFunction[object],
        hook_impl_opts: HookimplOpts,
    ) -> None:
        self.function: Final = function
        argnames, kwargnames = varnames(self.function)
        self.argnames: Final = argnames
        self.kwargnames: Final = kwargnames
        self.plugin: Final = plugin
        self.plugin_name: Final = plugin_name
        self.optionalhook: Final[bool] = hook_impl_opts["optionalhook"]
        self.tryfirst: Final[bool] = hook_impl_opts["tryfirst"]
        self.trylast: Final[bool] = hook_impl_opts["trylast"]

    @property
    @abstractmethod
    def is_wrapper(self) -> bool:
        """Whether this is a wrapper implementation."""
        ...

    def _get_args(self, caller_kwargs: Mapping[str, object]) -> list[object]:
        """Extract positional args from caller kwargs.

        :raises HookCallError: If a required argument is missing.
        """
        from ._result import HookCallError

        try:
            return [caller_kwargs[argname] for argname in self.argnames]
        except KeyError:
            for argname in self.argnames:
                if argname not in caller_kwargs:
                    raise HookCallError(f"hook call must provide argument {argname!r}")
            raise  # pragma: no cover

    # Backward compatibility properties - compute from type
    @property
    def wrapper(self) -> bool:
        """Whether this is a new-style wrapper."""
        return False

    @property
    def hookwrapper(self) -> bool:
        """Whether this is an old-style hookwrapper."""
        return False

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} "
            f"plugin_name={self.plugin_name!r}, plugin={self.plugin!r}>"
        )


@final
class _NormalHookImplementation(_HookImplementation):
    """A normal (non-wrapper) hook implementation."""

    __slots__ = ()

    @property
    def is_wrapper(self) -> bool:
        return False

    def call(self, caller_kwargs: Mapping[str, object]) -> object:
        """Call this hook implementation with the given kwargs."""
        args = self._get_args(caller_kwargs)
        return self.function(*args)


class _WrapperHookImplementation(_HookImplementation, ABC):
    """Base class for wrapper hook implementations."""

    __slots__ = ()

    @property
    def is_wrapper(self) -> bool:
        return True

    @abstractmethod
    def setup_teardown(self, caller_kwargs: Mapping[str, object]) -> Teardown:
        """Run the wrapper setup phase and return a teardown function.

        :param caller_kwargs: The keyword arguments from the hook call.

        The teardown function takes (result, exception) and returns
        (result, exception).
        """
        ...


def _gen_code_location(gen: Generator[None, object, object]) -> str:
    """Get code location string for a generator."""
    co = gen.gi_code  # type: ignore[attr-defined]
    return f"{co.co_name!r} {co.co_filename}:{co.co_firstlineno}"


@final
class _NewStyleWrapper(_WrapperHookImplementation):
    """New-style wrapper (wrapper=True)."""

    __slots__ = ()

    @property
    def wrapper(self) -> bool:
        return True

    def setup_teardown(self, caller_kwargs: Mapping[str, object]) -> Teardown:
        """Run the wrapper setup phase and return a teardown function."""
        args = self._get_args(caller_kwargs)
        gen: Generator[None, object, object] = self.function(*args)  # type: ignore[assignment]
        try:
            next(gen)
        except StopIteration:
            raise RuntimeError(
                f"wrap_controller at {_gen_code_location(gen)} did not yield"
            )

        def teardown(
            result: object, exception: BaseException | None
        ) -> tuple[object, BaseException | None]:
            __tracebackhide__ = True
            try:
                if exception is not None:
                    # Throw exception into generator
                    gen.throw(exception)
                else:
                    gen.send(result)
            except StopIteration as si:
                return si.value, None
            except RuntimeError as re:
                # StopIteration from generator causes RuntimeError in Python 3.7+
                # even for coroutine usage - see #544
                if isinstance(exception, StopIteration) and re.__cause__ is exception:
                    gen.close()
                    return None, exception
                return None, re
            except BaseException as e:
                return None, e
            # If we get here, the wrapper yielded again (bad)
            gen.close()
            return None, RuntimeError(
                f"wrap_controller at {_gen_code_location(gen)} has second yield"
            )

        return teardown


@final
class _OldStyleWrapper(_WrapperHookImplementation):
    """Legacy hookwrapper (hookwrapper=True)."""

    __slots__ = ()

    @property
    def hookwrapper(self) -> bool:
        return True

    def setup_teardown(self, caller_kwargs: Mapping[str, object]) -> Teardown:
        """Run the wrapper setup phase and return a teardown function."""
        import warnings

        from ._result import Result
        from ._warnings import PluggyTeardownRaisedWarning

        args = self._get_args(caller_kwargs)
        gen: Generator[None, Result[object], None]
        gen = self.function(*args)  # type: ignore[assignment]
        try:
            next(gen)
        except StopIteration:
            loc = _gen_code_location(gen)  # type: ignore[arg-type]
            raise RuntimeError(f"wrap_controller at {loc} did not yield")

        def teardown(
            result: object, exception: BaseException | None
        ) -> tuple[object, BaseException | None]:
            __tracebackhide__ = True
            # Old-style wrappers receive Result object
            result_obj = Result(result, exception)
            try:
                gen.send(result_obj)
            except StopIteration:
                # Old-style wrapper completed normally
                return result_obj._result, result_obj._exception
            except BaseException as e:
                # Warn about teardown exception in old-style wrapper
                loc = _gen_code_location(gen)  # type: ignore[arg-type]
                msg = (
                    "A plugin raised an exception during an "
                    "old-style hookwrapper teardown.\n"
                    f"Plugin: {self.plugin_name}, Hook: {loc}\n"
                    f"{type(e).__name__}: {e}\n"
                    "For more information see "
                    "https://pluggy.readthedocs.io/en/stable/api_reference.html"
                    "#pluggy.PluggyTeardownRaisedWarning"
                )
                warnings.warn(PluggyTeardownRaisedWarning(msg), stacklevel=5)
                return None, e
            finally:
                gen.close()
            # Unreachable - either StopIteration or exception
            loc = _gen_code_location(gen)  # type: ignore[arg-type]
            return None, RuntimeError(f"wrap_controller at {loc} has second yield")

        return teardown


def _create_hook_implementation(
    plugin: _Plugin,
    plugin_name: str,
    function: _HookImplFunction[object],
    hook_impl_opts: HookimplOpts,
) -> _HookImplementation:
    """Factory returning appropriate implementation type (internal)."""
    if hook_impl_opts.get("wrapper") and hook_impl_opts.get("hookwrapper"):
        from ._manager import PluginValidationError

        raise PluginValidationError(
            plugin,
            f"Plugin {plugin_name!r}\n"
            "The wrapper=True and hookwrapper=True options are mutually exclusive",
        )
    if hook_impl_opts.get("wrapper"):
        return _NewStyleWrapper(plugin, plugin_name, function, hook_impl_opts)
    elif hook_impl_opts.get("hookwrapper"):
        return _OldStyleWrapper(plugin, plugin_name, function, hook_impl_opts)
    else:
        return _NormalHookImplementation(plugin, plugin_name, function, hook_impl_opts)


@final
class HookImpl:
    """A hook implementation in a :class:`HookCaller`.

    .. deprecated::
        This class is deprecated. Use :class:`HookImplementationProtocol`
        for type hints instead.
    """

    __slots__ = (
        "function",
        "argnames",
        "kwargnames",
        "plugin",
        "opts",
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
        hook_impl_opts: HookimplOpts,
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
        #: The :class:`HookimplOpts` used to configure this hook implementation.
        self.opts: Final = hook_impl_opts
        #: The name of the plugin which defined this hook implementation.
        self.plugin_name: Final = plugin_name
        #: Whether the hook implementation is a :ref:`wrapper <hookwrapper>`.
        self.wrapper: Final = hook_impl_opts["wrapper"]
        #: Whether the hook implementation is an :ref:`old-style wrapper
        #: <old_style_hookwrappers>`.
        self.hookwrapper: Final = hook_impl_opts["hookwrapper"]
        #: Whether validation against a hook specification is :ref:`optional
        #: <optionalhook>`.
        self.optionalhook: Final = hook_impl_opts["optionalhook"]
        #: Whether to try to order this hook implementation :ref:`first
        #: <callorder>`.
        self.tryfirst: Final = hook_impl_opts["tryfirst"]
        #: Whether to try to order this hook implementation :ref:`last
        #: <callorder>`.
        self.trylast: Final = hook_impl_opts["trylast"]

    @property
    def is_wrapper(self) -> bool:
        """Whether this is a wrapper implementation."""
        return self.wrapper or self.hookwrapper

    def __repr__(self) -> str:
        return f"<HookImpl plugin_name={self.plugin_name!r}, plugin={self.plugin!r}>"


@final
class HookSpec:
    __slots__ = (
        "namespace",
        "function",
        "name",
        "argnames",
        "kwargnames",
        "opts",
        "warn_on_impl",
        "warn_on_impl_args",
    )

    def __init__(self, namespace: _Namespace, name: str, opts: HookspecOpts) -> None:
        self.namespace = namespace
        self.function: Callable[..., object] = getattr(namespace, name)
        self.name = name
        self.argnames, self.kwargnames = varnames(self.function)
        self.opts = opts
        self.warn_on_impl = opts.get("warn_on_impl")
        self.warn_on_impl_args = opts.get("warn_on_impl_args")
