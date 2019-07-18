"""
Internal hook annotation, representation and calling machinery.
"""
import inspect
import sys
import warnings
from .callers import _legacymulticall, _multicall

if False:  # TYPE_CHECKING
    from types import ModuleType
    from typing import Any
    from typing import Callable
    from typing import Dict
    from typing import List
    from typing import Optional
    from typing import Sequence
    from typing import Tuple
    from typing import TypeVar
    from typing import Union
    from typing import overload
    from typing_extensions import TypedDict

    from .callers import _HookImplFunction
    from .manager import _Plugin
    from ._tracing import TagTracerSub

    _F = TypeVar("_F", bound=Callable[..., object])
    _Namespace = Union[ModuleType, type]
    _HookSpecOpts = TypedDict(
        "_HookSpecOpts",
        {"firstresult": bool, "historic": bool, "warn_on_impl": Optional[Warning]},
    )
    _HookImplOpts = TypedDict(
        "_HookImplOpts",
        {"hookwrapper": bool, "optionalhook": bool, "tryfirst": bool, "trylast": bool},
    )
    _HookExec = Callable[
        ["_HookCaller", List["HookImpl"], Dict[str, object]],
        Union[object, List[object]],
    ]

    class _RelayType(object):
        def __getattr__(self, name):
            # type: (str) -> _HookCaller
            pass


else:

    def _overload_dummy(*args, **kwds):  # type: ignore
        raise NotImplementedError(
            "You should not call an overloaded function. "
            "A series of @overload-decorated functions "
            "outside a stub module should always be followed "
            "by an implementation that is not @overload-ed."
        )

    def overload(func):  # type: ignore
        return _overload_dummy

    _RelayType = object  # type: ignore


class HookspecMarker(object):
    """ Decorator helper class for marking functions as hook specifications.

    You can instantiate it with a project_name to get a decorator.
    Calling PluginManager.add_hookspecs later will discover all marked functions
    if the PluginManager uses the same project_name.
    """

    def __init__(self, project_name):
        # type: (str) -> None
        self.project_name = project_name

    @overload
    def __call__(
        self,
        function,  # type: _F
        firstresult=False,  # type: bool
        historic=False,  # type: bool
        warn_on_impl=None,  # type: Optional[Warning]
    ):
        # type: (...) -> _F
        pass

    @overload  # noqa: F811
    def __call__(
        self,
        function=None,  # type: None
        firstresult=False,  # type: bool
        historic=False,  # type: bool
        warn_on_impl=None,  # type: Optional[Warning]
    ):
        # type: (...) -> Callable[[_F], _F]
        pass

    def __call__(  # noqa: F811
        self,
        function=None,  # type: Optional[_F]
        firstresult=False,  # type: bool
        historic=False,  # type: bool
        warn_on_impl=None,  # type: Optional[Warning]
    ):
        # type: (...) -> Union[_F, Callable[[_F], _F]]
        """ if passed a function, directly sets attributes on the function
        which will make it discoverable to add_hookspecs().  If passed no
        function, returns a decorator which can be applied to a function
        later using the attributes supplied.

        If firstresult is True the 1:N hook call (N being the number of registered
        hook implementation functions) will stop at I<=N when the I'th function
        returns a non-None result.

        If historic is True calls to a hook will be memorized and replayed
        on later registered plugins.

        """

        def setattr_hookspec_opts(func):
            # type: (_F) -> _F
            if historic and firstresult:
                raise ValueError("cannot have a historic firstresult hook")
            opts = {
                "firstresult": firstresult,
                "historic": historic,
                "warn_on_impl": warn_on_impl,
            }  # type: _HookSpecOpts
            setattr(func, self.project_name + "_spec", opts)
            return func

        if function is not None:
            return setattr_hookspec_opts(function)
        else:
            return setattr_hookspec_opts


class HookimplMarker(object):
    """ Decorator helper class for marking functions as hook implementations.

    You can instantiate with a project_name to get a decorator.
    Calling PluginManager.register later will discover all marked functions
    if the PluginManager uses the same project_name.
    """

    def __init__(self, project_name):
        # type: (str) -> None
        self.project_name = project_name

    @overload
    def __call__(
        self,
        function,  # type: _F
        hookwrapper=False,  # type: bool
        optionalhook=False,  # type: bool
        tryfirst=False,  # type: bool
        trylast=False,  # type: bool
    ):
        # type: (...) -> _F
        pass

    @overload  # noqa: F811
    def __call__(
        self,
        function=None,  # type: None
        hookwrapper=False,  # type: bool
        optionalhook=False,  # type: bool
        tryfirst=False,  # type: bool
        trylast=False,  # type: bool
    ):
        # type: (...) -> Callable[[_F], _F]
        pass

    def __call__(  # noqa: F811
        self,
        function=None,  # type: Optional[_F]
        hookwrapper=False,  # type: bool
        optionalhook=False,  # type: bool
        tryfirst=False,  # type: bool
        trylast=False,  # type: bool
    ):
        # type: (...) -> Union[_F, Callable[[_F], _F]]
        """ if passed a function, directly sets attributes on the function
        which will make it discoverable to register().  If passed no function,
        returns a decorator which can be applied to a function later using
        the attributes supplied.

        If optionalhook is True a missing matching hook specification will not result
        in an error (by default it is an error if no matching spec is found).

        If tryfirst is True this hook implementation will run as early as possible
        in the chain of N hook implementations for a specfication.

        If trylast is True this hook implementation will run as late as possible
        in the chain of N hook implementations.

        If hookwrapper is True the hook implementations needs to execute exactly
        one "yield".  The code before the yield is run early before any non-hookwrapper
        function is run.  The code after the yield is run after all non-hookwrapper
        function have run.  The yield receives a ``_Result`` object representing
        the exception or result outcome of the inner calls (including other hookwrapper
        calls).

        """

        def setattr_hookimpl_opts(func):
            # type: (_F) -> _F
            opts = {
                "hookwrapper": hookwrapper,
                "optionalhook": optionalhook,
                "tryfirst": tryfirst,
                "trylast": trylast,
            }  # type: _HookImplOpts
            setattr(func, self.project_name + "_impl", opts)
            return func

        if function is None:
            return setattr_hookimpl_opts
        else:
            return setattr_hookimpl_opts(function)


def normalize_hookimpl_opts(opts):
    # type: (Dict[str, Any]) -> None
    opts.setdefault("tryfirst", False)
    opts.setdefault("trylast", False)
    opts.setdefault("hookwrapper", False)
    opts.setdefault("optionalhook", False)


_PYPY3 = hasattr(sys, "pypy_version_info") and sys.version_info.major == 3


def varnames(func):
    # type: (object) -> Tuple[Tuple[str, ...], Tuple[str, ...]]
    """Return tuple of positional and keywrord argument names for a function,
    method, class or callable.

    In case of a class, its ``__init__`` method is considered.
    For methods the ``self`` parameter is not included.
    """
    dummy_cache = {}  # type: Dict[str, object]
    cache = getattr(func, "__dict__", dummy_cache)  # type: Dict[str, object]
    try:
        return cache["_varnames"]  # type: ignore
    except KeyError:
        pass

    if inspect.isclass(func):
        try:
            func = func.__init__  # type: ignore
        except AttributeError:
            return (), ()
    elif not inspect.isroutine(func):  # callable object?
        try:
            func = getattr(func, "__call__", func)
        except Exception:
            return (), ()

    try:  # func MUST be a function or method here or we won't parse any args
        if hasattr(inspect, "getfullargspec"):
            spec = inspect.getfullargspec(
                func
            )  # type: Union[inspect.FullArgSpec, inspect.ArgSpec]
        else:
            spec = inspect.getargspec(func)
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
    if not _PYPY3:
        implicit_names = ("self",)  # type: Tuple[str, ...]
    else:
        implicit_names = ("self", "obj")
    if args:
        qualname = getattr(func, "__qualname__", "")  # type: str
        if inspect.ismethod(func) or ("." in qualname and args[0] in implicit_names):
            args = args[1:]

    try:
        cache["_varnames"] = args, kwargs
    except TypeError:
        pass
    return args, kwargs


class _HookRelay(_RelayType):
    """ hook holder object for performing 1:N hook calls where N is the number
    of registered plugins.

    """

    def __init__(self, trace):
        # type: (TagTracerSub) -> None
        self._trace = trace


class _HookCaller(object):
    def __init__(
        self,
        name,  # type: str
        hook_execute,  # type: _HookExec
        specmodule_or_class=None,  # type: Optional[_Namespace]
        spec_opts=None,  # type: Optional[_HookSpecOpts]
    ):
        # type: (...) -> None
        self.name = name
        self._wrappers = []  # type: List[HookImpl]
        self._nonwrappers = []  # type: List[HookImpl]
        self._hookexec = hook_execute
        self.argnames = None
        self.kwargnames = None
        self.multicall = _multicall
        self.spec = None  # type: Optional[HookSpec]
        if specmodule_or_class is not None:
            assert spec_opts is not None
            self.set_specification(specmodule_or_class, spec_opts)

    def has_spec(self):
        # type: () -> bool
        return self.spec is not None

    def set_specification(self, specmodule_or_class, spec_opts):
        # type: (_Namespace, _HookSpecOpts) -> None
        assert not self.has_spec()
        self.spec = HookSpec(specmodule_or_class, self.name, spec_opts)
        if spec_opts.get("historic"):
            self._call_history = (
                []
            )  # type: List[Tuple[Dict[str, object], Optional[Callable[[Any], None]]]]

    def is_historic(self):
        # type: () -> bool
        return hasattr(self, "_call_history")

    def _remove_plugin(self, plugin):
        # type: (_Plugin) -> None
        def remove(wrappers):
            # type: (List[HookImpl]) -> Optional[bool]
            for i, method in enumerate(wrappers):
                if method.plugin == plugin:
                    del wrappers[i]
                    return True
            return None

        if remove(self._wrappers) is None:
            if remove(self._nonwrappers) is None:
                raise ValueError("plugin %r not found" % (plugin,))

    def get_hookimpls(self):
        # type: () -> List[HookImpl]
        # Order is important for _hookexec
        return self._nonwrappers + self._wrappers

    def _add_hookimpl(self, hookimpl):
        # type: (HookImpl) -> None
        """Add an implementation to the callback chain.
        """
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

        if "__multicall__" in hookimpl.argnames:
            warnings.warn(
                "Support for __multicall__ is now deprecated and will be"
                "removed in an upcoming release.",
                DeprecationWarning,
            )
            self.multicall = _legacymulticall

    def __repr__(self):
        # type: () -> str
        return "<_HookCaller %r>" % (self.name,)

    def __call__(self, *args, **kwargs):
        # type: (object, object) -> Any
        if args:
            raise TypeError("hook calling supports only keyword arguments")
        assert not self.is_historic()
        if self.spec and self.spec.argnames:
            notincall = (
                set(self.spec.argnames) - set(["__multicall__"]) - set(kwargs.keys())
            )
            if notincall:
                warnings.warn(
                    "Argument(s) {} which are declared in the hookspec "
                    "can not be found in this hook call".format(tuple(notincall)),
                    stacklevel=2,
                )
        return self._hookexec(self, self.get_hookimpls(), kwargs)

    def call_historic(
        self,
        result_callback=None,  # type: Optional[Callable[[Any], None]]
        kwargs=None,  # type: Optional[Dict[str, object]]
        proc=None,  # type: Optional[Callable[[Any], None]]
    ):
        # type: (...) -> None
        """Call the hook with given ``kwargs`` for all registered plugins and
        for all plugins which will be registered afterwards.

        If ``result_callback`` is not ``None`` it will be called for for each
        non-None result obtained from a hook implementation.

        .. note::
            The ``proc`` argument is now deprecated.
        """
        if proc is not None:
            warnings.warn(
                "Support for `proc` argument is now deprecated and will be"
                "removed in an upcoming release.",
                DeprecationWarning,
            )
            result_callback = proc

        self._call_history.append((kwargs or {}, result_callback))
        # historizing hooks don't return results
        res = self._hookexec(self, self.get_hookimpls(), kwargs or {})
        if result_callback is None:
            return
        # XXX: remember firstresult isn't compat with historic
        assert isinstance(res, list)
        for x in res or []:
            result_callback(x)

    def call_extra(self, methods, kwargs):
        # type: (Sequence[Callable[..., object]], Dict[str, object]) -> Any
        """ Call the hook with some additional temporarily participating
        methods using the specified kwargs as call parameters. """
        old = list(self._nonwrappers), list(self._wrappers)
        for method in methods:
            opts = {
                "hookwrapper": False,
                "optionalhook": False,
                "trylast": False,
                "tryfirst": False,
            }  # type: _HookImplOpts
            hookimpl = HookImpl(None, "<temp>", method, opts)
            self._add_hookimpl(hookimpl)
        try:
            return self(**kwargs)
        finally:
            self._nonwrappers, self._wrappers = old

    def _maybe_apply_history(self, method):
        # type: (HookImpl) -> None
        """Apply call history to a new hookimpl if it is marked as historic.
        """
        if self.is_historic():
            for kwargs, result_callback in self._call_history:
                res = self._hookexec(self, [method], kwargs)
                if res and result_callback is not None:
                    # XXX: remember firstresult isn't compat with historic
                    assert isinstance(res, list)
                    result_callback(res[0])


class HookImpl(object):
    def __init__(self, plugin, plugin_name, function, hook_impl_opts):
        # type: (_Plugin, str, _HookImplFunction[object], _HookImplOpts) -> None
        self.function = function
        self.argnames, self.kwargnames = varnames(self.function)
        self.plugin = plugin
        self.opts = hook_impl_opts
        self.plugin_name = plugin_name
        self.hookwrapper = hook_impl_opts["hookwrapper"]
        self.optionalhook = hook_impl_opts["optionalhook"]
        self.tryfirst = hook_impl_opts["tryfirst"]
        self.trylast = hook_impl_opts["trylast"]

    def __repr__(self):
        # type: () -> str
        return "<HookImpl plugin_name=%r, plugin=%r>" % (self.plugin_name, self.plugin)


class HookSpec(object):
    def __init__(self, namespace, name, opts):
        # type: (_Namespace, str, _HookSpecOpts) -> None
        self.namespace = namespace
        function = getattr(namespace, name)  # type: Callable[..., object]
        self.function = function
        self.name = name
        argnames, self.kwargnames = varnames(function)
        self.opts = opts
        self.argnames = ["__multicall__"] + list(argnames)
        self.warn_on_impl = opts.get("warn_on_impl")
