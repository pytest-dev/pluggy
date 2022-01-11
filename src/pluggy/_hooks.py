"""
Internal hook annotation, representation and calling machinery.
"""
import inspect
import sys
import warnings
from types import ModuleType
from typing import (
    Any,
    Callable,
    Generator,
    List,
    Mapping,
    Optional,
    overload,
    Sequence,
    Tuple,
    TypeVar,
    TYPE_CHECKING,
    Union,
)

from ._result import _Result

if TYPE_CHECKING:
    from typing_extensions import TypedDict


_T = TypeVar("_T")
_F = TypeVar("_F", bound=Callable[..., object])
_Namespace = Union[ModuleType, type]
_Plugin = object
_HookExec = Callable[
    [str, Sequence["HookImpl"], Mapping[str, object], bool],
    Union[object, List[object]],
]
_HookImplFunction = Callable[..., Union[_T, Generator[None, _Result[_T], None]]]
if TYPE_CHECKING:

    class _HookSpecOpts(TypedDict):
        firstresult: bool
        historic: bool
        warn_on_impl: Optional[Warning]

    class _HookImplOpts(TypedDict):
        hookwrapper: bool
        optionalhook: bool
        tryfirst: bool
        trylast: bool
        specname: Optional[str]


class HookspecMarker:
    """Decorator helper class for marking functions as hook specifications.

    You can instantiate it with a project_name to get a decorator.
    Calling :py:meth:`.PluginManager.add_hookspecs` later will discover all marked functions
    if the :py:class:`.PluginManager` uses the same project_name.
    """

    def __init__(self, project_name: str) -> None:
        self.project_name = project_name

    @overload
    def __call__(
        self,
        function: _F,
        firstresult: bool = False,
        historic: bool = False,
        warn_on_impl: Optional[Warning] = None,
    ) -> _F:
        ...

    @overload  # noqa: F811
    def __call__(  # noqa: F811
        self,
        function: None = ...,
        firstresult: bool = ...,
        historic: bool = ...,
        warn_on_impl: Optional[Warning] = ...,
    ) -> Callable[[_F], _F]:
        ...

    def __call__(  # noqa: F811
        self,
        function: Optional[_F] = None,
        firstresult: bool = False,
        historic: bool = False,
        warn_on_impl: Optional[Warning] = None,
    ) -> Union[_F, Callable[[_F], _F]]:
        """if passed a function, directly sets attributes on the function
        which will make it discoverable to :py:meth:`.PluginManager.add_hookspecs`.
        If passed no function, returns a decorator which can be applied to a function
        later using the attributes supplied.

        If ``firstresult`` is ``True`` the 1:N hook call (N being the number of registered
        hook implementation functions) will stop at I<=N when the I'th function
        returns a non-``None`` result.

        If ``historic`` is ``True`` calls to a hook will be memorized and replayed
        on later registered plugins.

        """

        def setattr_hookspec_opts(func: _F) -> _F:
            if historic and firstresult:
                raise ValueError("cannot have a historic firstresult hook")
            opts: "_HookSpecOpts" = {
                "firstresult": firstresult,
                "historic": historic,
                "warn_on_impl": warn_on_impl,
            }
            setattr(func, self.project_name + "_spec", opts)
            return func

        if function is not None:
            return setattr_hookspec_opts(function)
        else:
            return setattr_hookspec_opts


class HookimplMarker:
    """Decorator helper class for marking functions as hook implementations.

    You can instantiate with a ``project_name`` to get a decorator.
    Calling :py:meth:`.PluginManager.register` later will discover all marked functions
    if the :py:class:`.PluginManager` uses the same project_name.
    """

    def __init__(self, project_name: str) -> None:
        self.project_name = project_name

    @overload
    def __call__(
        self,
        function: _F,
        hookwrapper: bool = ...,
        optionalhook: bool = ...,
        tryfirst: bool = ...,
        trylast: bool = ...,
        specname: Optional[str] = ...,
    ) -> _F:
        ...

    @overload  # noqa: F811
    def __call__(  # noqa: F811
        self,
        function: None = ...,
        hookwrapper: bool = ...,
        optionalhook: bool = ...,
        tryfirst: bool = ...,
        trylast: bool = ...,
        specname: Optional[str] = ...,
    ) -> Callable[[_F], _F]:
        ...

    def __call__(  # noqa: F811
        self,
        function: Optional[_F] = None,
        hookwrapper: bool = False,
        optionalhook: bool = False,
        tryfirst: bool = False,
        trylast: bool = False,
        specname: Optional[str] = None,
    ) -> Union[_F, Callable[[_F], _F]]:
        """if passed a function, directly sets attributes on the function
        which will make it discoverable to :py:meth:`.PluginManager.register`.
        If passed no function, returns a decorator which can be applied to a
        function later using the attributes supplied.

        If ``optionalhook`` is ``True`` a missing matching hook specification will not result
        in an error (by default it is an error if no matching spec is found).

        If ``tryfirst`` is ``True`` this hook implementation will run as early as possible
        in the chain of N hook implementations for a specification.

        If ``trylast`` is ``True`` this hook implementation will run as late as possible
        in the chain of N hook implementations.

        If ``hookwrapper`` is ``True`` the hook implementations needs to execute exactly
        one ``yield``.  The code before the ``yield`` is run early before any non-hookwrapper
        function is run.  The code after the ``yield`` is run after all non-hookwrapper
        function have run.  The ``yield`` receives a :py:class:`.callers._Result` object
        representing the exception or result outcome of the inner calls (including other
        hookwrapper calls).

        If ``specname`` is provided, it will be used instead of the function name when
        matching this hook implementation to a hook specification during registration.

        """

        def setattr_hookimpl_opts(func: _F) -> _F:
            opts: "_HookImplOpts" = {
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


def normalize_hookimpl_opts(opts: "_HookImplOpts") -> None:
    opts.setdefault("tryfirst", False)
    opts.setdefault("trylast", False)
    opts.setdefault("hookwrapper", False)
    opts.setdefault("optionalhook", False)
    opts.setdefault("specname", None)


_PYPY = hasattr(sys, "pypy_version_info")


def varnames(func: object) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Return tuple of positional and keywrord argument names for a function,
    method, class or callable.

    In case of a class, its ``__init__`` method is considered.
    For methods the ``self`` parameter is not included.
    """
    if inspect.isclass(func):
        try:
            func = func.__init__
        except AttributeError:
            return (), ()
    elif not inspect.isroutine(func):  # callable object?
        try:
            func = getattr(func, "__call__", func)
        except Exception:
            return (), ()

    try:  # func MUST be a function or method here or we won't parse any args
        spec = inspect.getfullargspec(func)
    except TypeError:
        return (), ()

    args, defaults = tuple(spec.args), spec.defaults
    if defaults:
        index = -len(defaults)
        args, kwargs = args[:index], tuple(args[index:])
    else:
        kwargs = ()

    # strip any implicit instance arg
    # pypy3 uses "obj" instead of "self" for default dunder methods
    if not _PYPY:
        implicit_names: Tuple[str, ...] = ("self",)
    else:
        implicit_names = ("self", "obj")
    if args:
        qualname: str = getattr(func, "__qualname__", "")
        if inspect.ismethod(func) or ("." in qualname and args[0] in implicit_names):
            args = args[1:]

    return args, kwargs


class _HookRelay:
    """hook holder object for performing 1:N hook calls where N is the number
    of registered plugins.

    """

    if TYPE_CHECKING:

        def __getattr__(self, name: str) -> "_HookCaller":
            ...


class _HookCaller:
    def __init__(
        self,
        name: str,
        hook_execute: _HookExec,
        spec_argnames: Optional[Tuple[str, ...]] = None,
        spec_opts: Optional["_HookSpecOpts"] = None,
    ) -> None:
        self.name = name
        self._wrappers: List[HookImpl] = []
        self._nonwrappers: List[HookImpl] = []
        self._hookexec = hook_execute
        self._call_history: Optional[
            List[Tuple[Mapping[str, object], Optional[Callable[[Any], None]]]]
        ] = None
        self.spec_argnames = spec_argnames
        self.spec_opts = spec_opts

    def has_spec(self) -> bool:
        return self.spec_opts is not None

    def set_specification(
        self,
        specmodule_or_class: _Namespace,
        spec_opts: "_HookSpecOpts",
    ) -> None:
        assert not self.has_spec()

        spec_function: Callable[..., object] = getattr(specmodule_or_class, self.name)
        self.spec_argnames, spec_kwargnames = varnames(spec_function)
        self.spec_opts = spec_opts

        if spec_opts.get("historic"):
            self._call_history = []

    @property
    def warn_on_impl(self) -> Optional[Warning]:
        if self.spec_opts is None:
            return None
        return self.spec_opts.get("warn_on_impl")

    def is_historic(self) -> bool:
        return self._call_history is not None

    def _remove_plugin(self, plugin: _Plugin) -> None:
        def remove(wrappers: List[HookImpl]) -> Optional[bool]:
            for i, method in enumerate(wrappers):
                if method.plugin == plugin:
                    del wrappers[i]
                    return True
            return None

        if remove(self._wrappers) is None:
            if remove(self._nonwrappers) is None:
                raise ValueError(f"plugin {plugin!r} not found")

    def get_hookimpls(self) -> List["HookImpl"]:
        # Order is important for _hookexec
        return self._nonwrappers + self._wrappers

    def _add_hookimpl(self, hookimpl: "HookImpl") -> None:
        """Add an implementation to the callback chain."""
        if hookimpl.hookwrapper:
            methods = self._wrappers
        else:
            methods = self._nonwrappers

        if hookimpl.trylast:
            methods.insert(0, hookimpl)
        elif hookimpl.tryfirst:
            methods.append(hookimpl)
        else:
            # find last non-tryfirst method
            i = len(methods) - 1
            while i >= 0 and methods[i].tryfirst:
                i -= 1
            methods.insert(i + 1, hookimpl)

    def __repr__(self) -> str:
        return f"<_HookCaller {self.name!r}>"

    def __call__(self, *args: object, **kwargs: object) -> Any:
        if args:
            raise TypeError("hook calling supports only keyword arguments")
        assert not self.is_historic()

        # This is written to avoid expensive operations when not needed.
        if self.spec_opts is not None:
            assert self.spec_argnames is not None
            for argname in self.spec_argnames:
                if argname not in kwargs:
                    notincall = tuple(set(self.spec_argnames) - kwargs.keys())
                    warnings.warn(
                        "Argument(s) {} which are declared in the hookspec "
                        "can not be found in this hook call".format(notincall),
                        stacklevel=2,
                    )
                    break

            firstresult = self.spec_opts.get("firstresult", False)
        else:
            firstresult = False

        return self._hookexec(self.name, self.get_hookimpls(), kwargs, firstresult)

    def call_historic(
        self,
        result_callback: Optional[Callable[[Any], None]] = None,
        kwargs: Optional[Mapping[str, object]] = None,
    ) -> None:
        """Call the hook with given ``kwargs`` for all registered plugins and
        for all plugins which will be registered afterwards.

        If ``result_callback`` is not ``None`` it will be called for for each
        non-``None`` result obtained from a hook implementation.
        """
        assert self._call_history is not None
        kwargs = kwargs or {}
        self._call_history.append((kwargs, result_callback))
        # Historizing hooks don't return results.
        # Remember firstresult isn't compatible with historic.
        res = self._hookexec(self.name, self.get_hookimpls(), kwargs, False)
        if result_callback is None:
            return
        if isinstance(res, list):
            for x in res:
                result_callback(x)

    def call_extra(
        self, methods: Sequence[Callable[..., object]], kwargs: Mapping[str, object]
    ) -> Any:
        """Call the hook with some additional temporarily participating
        methods using the specified ``kwargs`` as call parameters."""
        old = list(self._nonwrappers), list(self._wrappers)
        for method in methods:
            opts: "_HookImplOpts" = {
                "hookwrapper": False,
                "optionalhook": False,
                "trylast": False,
                "tryfirst": False,
                "specname": None,
            }
            hookimpl = HookImpl(None, "<temp>", method, opts)
            self._add_hookimpl(hookimpl)
        try:
            return self(**kwargs)
        finally:
            self._nonwrappers, self._wrappers = old

    def _maybe_apply_history(self, method: "HookImpl") -> None:
        """Apply call history to a new hookimpl if it is marked as historic."""
        if self.is_historic():
            assert self._call_history is not None
            for kwargs, result_callback in self._call_history:
                res = self._hookexec(self.name, [method], kwargs, False)
                if res and result_callback is not None:
                    # XXX: remember firstresult isn't compat with historic
                    assert isinstance(res, list)
                    result_callback(res[0])


class HookImpl:
    def __init__(
        self,
        plugin: _Plugin,
        plugin_name: str,
        function: _HookImplFunction[object],
        hook_impl_opts: "_HookImplOpts",
    ) -> None:
        self.function = function
        self.argnames, self.kwargnames = varnames(self.function)
        self.plugin = plugin
        self.opts = hook_impl_opts
        self.plugin_name = plugin_name
        self.hookwrapper = hook_impl_opts["hookwrapper"]
        self.optionalhook = hook_impl_opts["optionalhook"]
        self.tryfirst = hook_impl_opts["tryfirst"]
        self.trylast = hook_impl_opts["trylast"]

    def __repr__(self) -> str:
        return f"<HookImpl plugin_name={self.plugin_name!r}, plugin={self.plugin!r}>"
