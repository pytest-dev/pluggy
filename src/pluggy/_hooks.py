"""
Internal hook annotation, representation and calling machinery.
"""
import warnings
from typing import (
    Callable,
    List,
    Optional,
    Tuple,
    Dict,
    overload,
    Union,
    TYPE_CHECKING,
    cast,
)
from types import FunctionType
from typing_extensions import Literal, TypedDict
from ._inspect import varnames
from ._result import HookFunction, SomeResult
from ._callers import HookArgs, HookResultCallback

if TYPE_CHECKING:
    from ._manager import HookExecCallable


class HookSpecMarkerData(TypedDict):
    firstresult: bool
    historic: bool
    warn_on_impl: Optional[Warning]


class HookspecMarker:
    """Decorator helper class for marking functions as hook specifications.

    You can instantiate it with a project_name to get a decorator.
    Calling :py:meth:`.PluginManager.add_hookspecs` later will discover all marked functions
    if the :py:class:`.PluginManager` uses the same project_name.
    """

    project_name: str

    def __init__(self, project_name: str) -> None:
        self.project_name = project_name

    @overload
    def __call__(
        self,
        function: Literal[None] = None,
        firstresult: bool = False,
        historic: bool = False,
        warn_on_impl: Optional[Warning] = None,
    ) -> Callable[[HookFunction], HookFunction]:
        pass

    @overload
    def __call__(
        self,
        function: HookFunction,
        firstresult: bool = False,
        historic: bool = False,
        warn_on_impl: Optional[Warning] = None,
    ) -> HookFunction:
        pass

    def __call__(
        self,
        function: Optional[HookFunction] = None,
        firstresult: bool = False,
        historic: bool = False,
        warn_on_impl: Optional[Warning] = None,
    ) -> Union[HookFunction, Callable[[HookFunction], HookFunction]]:
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

        def setattr_hookspec_opts(func: HookFunction) -> HookFunction:
            if historic and firstresult:
                raise ValueError("cannot have a historic firstresult hook")
            setattr(
                func,
                self.project_name + "_spec",
                HookSpecMarkerData(
                    firstresult=firstresult,
                    historic=historic,
                    warn_on_impl=warn_on_impl,
                ),
            )
            return func

        if function is not None:
            return setattr_hookspec_opts(function)
        else:
            return setattr_hookspec_opts


class HookImplMarkerSpec(TypedDict):
    hookwrapper: bool
    optionalhook: bool
    tryfirst: bool
    trylast: bool
    specname: Optional[str]


class HookimplMarker:
    """Decorator helper class for marking functions as hook implementations.

    You can instantiate with a ``project_name`` to get a decorator.
    Calling :py:meth:`.PluginManager.register` later will discover all marked functions
    if the :py:class:`.PluginManager` uses the same project_name.
    """

    project_name: str

    def __init__(self, project_name: str):
        self.project_name = project_name

    def __call__(
        self,
        function: Optional[HookFunction] = None,
        hookwrapper: bool = False,
        optionalhook: bool = False,
        tryfirst: bool = False,
        trylast: bool = False,
        specname: Optional[str] = None,
    ) -> Union[HookFunction, Callable[[HookFunction], HookFunction]]:

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

        def setattr_hookimpl_opts(func: HookFunction) -> HookFunction:
            setattr(
                func,
                self.project_name + "_impl",
                HookImplMarkerSpec(
                    hookwrapper=hookwrapper,
                    optionalhook=optionalhook,
                    tryfirst=tryfirst,
                    trylast=trylast,
                    specname=specname,
                ),
            )
            return func

        if function is None:
            return setattr_hookimpl_opts
        else:
            return setattr_hookimpl_opts(function)


def normalize_hookimpl_opts(
    opts: Union[HookImplMarkerSpec, Dict[str, Union[bool, str, None]]]
) -> None:
    opts.setdefault("tryfirst", False)
    opts.setdefault("trylast", False)
    opts.setdefault("hookwrapper", False)
    opts.setdefault("optionalhook", False)
    opts.setdefault("specname", None)


class _HookRelay:
    """hook holder object for performing 1:N hook calls where N is the number
    of registered plugins.

    """

    __dict__: Dict[str, "_HookCaller"]


class _HookCaller:
    name: str
    _wrappers: List["HookImpl"]
    _nonwrappers: List["HookImpl"]
    spec: Optional["HookSpec"]
    _call_history: Optional[
        List[
            Tuple[HookArgs, Optional[HookResultCallback]],
        ]
    ]

    def __init__(
        self,
        name: str,
        hook_execute: "HookExecCallable",
        specmodule_or_class: Optional[object] = None,
        spec_opts: Optional[HookSpecMarkerData] = None,
    ):
        self.name = name
        self._wrappers = []
        self._nonwrappers = []
        self._hookexec = hook_execute
        self._call_history = None
        self.spec = None
        if specmodule_or_class is not None:
            assert spec_opts is not None
            self.set_specification(specmodule_or_class, spec_opts)

    def has_spec(self) -> bool:
        return self.spec is not None

    def set_specification(
        self, specmodule_or_class: object, spec_opts: HookSpecMarkerData
    ) -> None:
        assert self.spec is None
        self.spec = HookSpec(specmodule_or_class, self.name, spec_opts)
        if spec_opts.get("historic"):
            self._call_history = []

    def is_historic(self) -> bool:
        return self._call_history is not None

    def _remove_plugin(self, plugin: object) -> None:
        def remove(wrappers: List[HookImpl]) -> bool:
            for i, method in enumerate(wrappers):
                if method.plugin == plugin:
                    del wrappers[i]
                    return True
            return False

        if not remove(self._wrappers):
            if not remove(self._nonwrappers):
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

    def __call__(
        self, *args: object, **kwargs: object
    ) -> Union[List[SomeResult], SomeResult]:
        if args:
            raise TypeError("hook calling supports only keyword arguments")
        assert not self.is_historic()

        # This is written to avoid expensive operations when not needed.
        if self.spec is not None:
            for argname in self.spec.argnames:
                if argname not in kwargs:
                    notincall = tuple(set(self.spec.argnames) - kwargs.keys())
                    warnings.warn(
                        "Argument(s) {} which are declared in the hookspec "
                        "can not be found in this hook call".format(notincall),
                        stacklevel=2,
                    )
                    break

            firstresult = cast(bool, self.spec.opts.get("firstresult"))
        else:
            firstresult = False

        return self._hookexec(self.name, self.get_hookimpls(), kwargs, firstresult)

    def call_historic(
        self,
        result_callback: Optional[HookResultCallback] = None,
        kwargs: Optional[HookArgs] = None,
    ) -> None:
        """Call the hook with given ``kwargs`` for all registered plugins and
        for all plugins which will be registered afterwards.

        If ``result_callback`` is not ``None`` it will be called for for each
        non-``None`` result obtained from a hook implementation.
        """
        assert self._call_history is not None
        self._call_history.append((kwargs or {}, result_callback))
        # Historizing hooks don't return results.
        # Remember firstresult isn't compatible with historic.

        res = self._hookexec(self.name, self.get_hookimpls(), kwargs or {}, False)
        if result_callback is None:
            return
        assert isinstance(res, list)
        for x in res:
            result_callback(x)

    def call_extra(
        self, methods: List[HookFunction], kwargs: HookArgs
    ) -> Union[List[SomeResult], SomeResult]:
        """Call the hook with some additional temporarily participating
        methods using the specified ``kwargs`` as call parameters."""
        old = list(self._nonwrappers), list(self._wrappers)
        for method in methods:
            opts = HookImplMarkerSpec(
                hookwrapper=False,
                trylast=False,
                tryfirst=False,
                specname=None,
                optionalhook=False,
            )
            hookimpl = HookImpl(None, "<temp>", method, opts)
            self._add_hookimpl(hookimpl)
        try:
            return self(**kwargs)
        finally:
            self._nonwrappers, self._wrappers = old

    def _maybe_apply_history(self, method: "HookImpl") -> None:
        """Apply call history to a new hookimpl if it is marked as historic."""
        if self._call_history is not None:
            for kwargs, result_callback in self._call_history:
                res = self._hookexec(self.name, [method], kwargs, False)
                assert isinstance(res, list)
                if res and result_callback is not None:
                    result_callback(res[0])


class HookImpl:
    function: HookFunction
    argnames: Tuple[str, ...]
    kwargnames: Tuple[str, ...]
    plugin: object
    plugin_name: str
    hookwrapper: bool
    tryfirst: bool
    trylast: bool
    optionalhook: bool

    def __init__(
        self,
        plugin: object,
        plugin_name: str,
        function: HookFunction,
        hook_impl_opts: HookImplMarkerSpec,
    ):
        self.function = function  # type: ignore
        self.argnames, self.kwargnames = varnames(function)
        self.plugin = plugin
        self.opts = hook_impl_opts
        self.plugin_name = plugin_name
        self.tryfirst = hook_impl_opts["tryfirst"]
        self.trylast = hook_impl_opts["trylast"]
        self.hookwrapper = hook_impl_opts["hookwrapper"]
        self.optionalhook = hook_impl_opts["optionalhook"]

    def __repr__(self) -> str:
        return f"<HookImpl plugin_name={self.plugin_name!r}, plugin={self.plugin!r}>"


class HookSpec:
    namespace: object
    function: object
    name: str
    argnames: Tuple[str, ...]
    kwargnames: Tuple[str, ...]
    opts: HookSpecMarkerData
    warn_on_impl: Optional[Warning]

    def __init__(self, namespace: object, name: str, opts: HookSpecMarkerData):
        self.namespace = namespace
        self.function = function = cast(object, getattr(namespace, name))
        self.name = name
        self.argnames, self.kwargnames = varnames(cast(FunctionType, function))
        self.opts = opts
        self.warn_on_impl = opts.get("warn_on_impl")
