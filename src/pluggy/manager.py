import inspect
import sys
from . import _tracing
from .hooks import HookImpl, _HookRelay, _HookCaller, normalize_hookimpl_opts
import warnings

if sys.version_info >= (3, 8):
    from importlib import metadata
else:
    import importlib_metadata as metadata

if False:  # TYPE_CHECKING
    from typing import Any
    from typing import Callable
    from typing import Dict
    from typing import Iterable
    from typing import List
    from typing import Optional
    from typing import Set
    from typing import Tuple
    from typing import Union

    from .hooks import HookSpec
    from .hooks import _HookSpecOpts
    from .hooks import _Namespace
    from ._tracing import _Result

    _Plugin = object


def _warn_for_function(warning, function):
    # type: (Warning, Callable[..., object]) -> None
    warnings.warn_explicit(
        warning,
        type(warning),
        lineno=function.__code__.co_firstlineno,
        filename=function.__code__.co_filename,
    )


class PluginValidationError(Exception):
    """ plugin failed validation.

    :param object plugin: the plugin which failed validation,
        may be a module or an arbitrary object.
    """

    def __init__(self, plugin, message):
        # type: (_Plugin, str) -> None
        self.plugin = plugin
        super(Exception, self).__init__(message)


class DistFacade(object):
    """Emulate a pkg_resources Distribution"""

    # Type ignored because importlib_metadata doesn't have stubs yet.
    def __init__(self, dist):  # type: ignore
        self._dist = dist

    @property
    def project_name(self):
        # type: () -> str
        return self.metadata["name"]  # type: ignore

    def __getattr__(self, attr, default=None):  # type: ignore
        return getattr(self._dist, attr, default)

    def __dir__(self):
        # type: () -> List[str]
        return sorted(dir(self._dist) + ["_dist", "project_name"])


class PluginManager(object):
    """ Core Pluginmanager class which manages registration
    of plugin objects and 1:N hook calling.

    You can register new hooks by calling ``add_hookspecs(module_or_class)``.
    You can register plugin objects (which contain hooks) by calling
    ``register(plugin)``.  The Pluginmanager is initialized with a
    prefix that is searched for in the names of the dict of registered
    plugin objects.

    For debugging purposes you can call ``enable_tracing()``
    which will subsequently send debug information to the trace helper.
    """

    def __init__(self, project_name, implprefix=None):
        # type: (str, Optional[str]) -> None
        """If ``implprefix`` is given implementation functions
        will be recognized if their name matches the implprefix. """
        self.project_name = project_name
        self._name2plugin = {}  # type: Dict[str, _Plugin]
        self._plugin2hookcallers = {}  # type: Dict[_Plugin, List[_HookCaller]]
        self._plugin_distinfo = []  # type: List[Tuple[_Plugin, DistFacade]]
        self.trace = _tracing.TagTracer().get("pluginmanage")
        self.hook = _HookRelay(self.trace.root.get("hook"))
        if implprefix is not None:
            warnings.warn(
                "Support for the `implprefix` arg is now deprecated and will "
                "be removed in an upcoming release. Please use HookimplMarker.",
                DeprecationWarning,
                stacklevel=2,
            )
        self._implprefix = implprefix

        def _inner_hookexec(hook, methods, kwargs):
            # type: (_HookCaller, List[HookImpl], Dict[str, object]) -> Union[object, List[object]]
            firstresult = hook.spec.opts["firstresult"] if hook.spec else False
            return hook.multicall(methods, kwargs, firstresult=firstresult)

        self._inner_hookexec = _inner_hookexec

    def _hookexec(self, hook, methods, kwargs):
        # type: (_HookCaller, List[HookImpl], Dict[str, object]) -> Union[object, List[object]]
        # called from all hookcaller instances.
        # enable_tracing will set its own wrapping function at self._inner_hookexec
        return self._inner_hookexec(hook, methods, kwargs)

    def register(self, plugin, name=None):
        # type: (_Plugin, Optional[str]) -> Optional[str]
        """ Register a plugin and return its canonical name or None if the name
        is blocked from registering.  Raise a ValueError if the plugin is already
        registered. """
        plugin_name = name or self.get_canonical_name(plugin)

        if plugin_name in self._name2plugin or plugin in self._plugin2hookcallers:
            if self._name2plugin.get(plugin_name, -1) is None:
                return None  # blocked plugin, return None to indicate no registration
            raise ValueError(
                "Plugin already registered: %s=%s\n%s"
                % (plugin_name, plugin, self._name2plugin)
            )

        # XXX if an error happens we should make sure no state has been
        # changed at point of return
        self._name2plugin[plugin_name] = plugin

        # register matching hook implementations of the plugin
        hookcallers = []  # type: List[_HookCaller]
        self._plugin2hookcallers[plugin] = hookcallers
        for name in dir(plugin):
            hookimpl_opts = self.parse_hookimpl_opts(plugin, name)
            if hookimpl_opts is not None:
                normalize_hookimpl_opts(hookimpl_opts)
                method = getattr(plugin, name)  # type: Callable[..., object]
                hookimpl = HookImpl(  # type: ignore
                    plugin, plugin_name, method, hookimpl_opts
                )
                hook = getattr(self.hook, name, None)  # type: Optional[_HookCaller]
                if hook is None:
                    hook = _HookCaller(name, self._hookexec)
                    setattr(self.hook, name, hook)
                elif hook.has_spec():
                    self._verify_hook(hook, hookimpl)
                    hook._maybe_apply_history(hookimpl)
                hook._add_hookimpl(hookimpl)
                hookcallers.append(hook)
        return plugin_name

    def parse_hookimpl_opts(self, plugin, name):
        # type: (_Plugin, str) -> Optional[Dict[str, Any]]
        method = getattr(plugin, name)  # type: Callable[..., object]
        if not inspect.isroutine(method):
            return None
        try:
            res = getattr(
                method, self.project_name + "_impl", None
            )  # type: Optional[Dict[str, Any]]
        except Exception:
            res = {}
        if res is not None and not isinstance(res, dict):
            # false positive
            res = None
        # TODO: remove when we drop implprefix in 1.0
        elif res is None and self._implprefix and name.startswith(self._implprefix):
            _warn_for_function(
                DeprecationWarning(
                    "The `implprefix` system is deprecated please decorate "
                    "this function using an instance of HookimplMarker."
                ),
                method,
            )
            res = {}
        return res

    def unregister(self, plugin=None, name=None):
        # type: (Optional[_Plugin], Optional[str]) -> _Plugin
        """ unregister a plugin object and all its contained hook implementations
        from internal data structures. """
        if name is None:
            assert plugin is not None, "one of name or plugin needs to be specified"
            name = self.get_name(plugin)
            assert name is not None, "plugin is not registered"

        if plugin is None:
            plugin = self.get_plugin(name)

        # if self._name2plugin[name] == None registration was blocked: ignore
        if self._name2plugin.get(name):
            assert name is not None
            del self._name2plugin[name]

        for hookcaller in self._plugin2hookcallers.pop(plugin, []):
            hookcaller._remove_plugin(plugin)

        return plugin

    def set_blocked(self, name):
        # type: (str) -> None
        """ block registrations of the given name, unregister if already registered. """
        self.unregister(name=name)
        self._name2plugin[name] = None

    def is_blocked(self, name):
        # type: (str) -> bool
        """ return True if the given plugin name is blocked. """
        return name in self._name2plugin and self._name2plugin[name] is None

    def add_hookspecs(self, module_or_class):
        # type: (_Namespace) -> None
        """ add new hook specifications defined in the given module_or_class.
        Functions are recognized if they have been decorated accordingly. """
        names = []
        for name in dir(module_or_class):
            spec_opts = self.parse_hookspec_opts(module_or_class, name)
            if spec_opts is not None:
                hc = getattr(self.hook, name, None)  # type: Optional[_HookCaller]
                if hc is None:
                    hc = _HookCaller(name, self._hookexec, module_or_class, spec_opts)
                    setattr(self.hook, name, hc)
                else:
                    # plugins registered this hook without knowing the spec
                    hc.set_specification(module_or_class, spec_opts)
                    for hookfunction in hc.get_hookimpls():
                        self._verify_hook(hc, hookfunction)
                names.append(name)

        if not names:
            raise ValueError(
                "did not find any %r hooks in %r" % (self.project_name, module_or_class)
            )

    def parse_hookspec_opts(self, module_or_class, name):
        # type: (_Namespace, str) -> Optional[_HookSpecOpts]
        method = getattr(module_or_class, name)  # type: HookSpec
        opts = getattr(
            method, self.project_name + "_spec", None
        )  # type: Optional[_HookSpecOpts]
        return opts

    def get_plugins(self):
        # type: () -> Set[_Plugin]
        """ return the set of registered plugins. """
        return set(self._plugin2hookcallers)

    def is_registered(self, plugin):
        # type: (_Plugin) -> bool
        """ Return True if the plugin is already registered. """
        return plugin in self._plugin2hookcallers

    def get_canonical_name(self, plugin):
        # type: (_Plugin) -> str
        """ Return canonical name for a plugin object. Note that a plugin
        may be registered under a different name which was specified
        by the caller of register(plugin, name). To obtain the name
        of an registered plugin use ``get_name(plugin)`` instead."""
        __name__ = getattr(plugin, "__name__", None)  # type: Optional[str]
        return __name__ or str(id(plugin))

    def get_plugin(self, name):
        # type: (str) -> Optional[_Plugin]
        """ Return a plugin or None for the given name. """
        return self._name2plugin.get(name)

    def has_plugin(self, name):
        # type: (str) -> bool
        """ Return True if a plugin with the given name is registered. """
        return self.get_plugin(name) is not None

    def get_name(self, plugin):
        # type: (_Plugin) -> Optional[str]
        """ Return name for registered plugin or None if not registered. """
        for name, val in self._name2plugin.items():
            if plugin == val:
                return name
        return None

    def _verify_hook(self, hook, hookimpl):
        # type: (_HookCaller, HookImpl) -> None
        if hook.is_historic() and hookimpl.hookwrapper:
            raise PluginValidationError(
                hookimpl.plugin,
                "Plugin %r\nhook %r\nhistoric incompatible to hookwrapper"
                % (hookimpl.plugin_name, hook.name),
            )
        assert hook.spec is not None
        if hook.spec.warn_on_impl:
            _warn_for_function(hook.spec.warn_on_impl, hookimpl.function)
        # positional arg checking
        notinspec = set(hookimpl.argnames) - set(hook.spec.argnames)
        if notinspec:
            raise PluginValidationError(
                hookimpl.plugin,
                "Plugin %r for hook %r\nhookimpl definition: %s\n"
                "Argument(s) %s are declared in the hookimpl but "
                "can not be found in the hookspec"
                % (
                    hookimpl.plugin_name,
                    hook.name,
                    _formatdef(hookimpl.function),
                    notinspec,
                ),
            )

    def check_pending(self):
        # type: () -> None
        """ Verify that all hooks which have not been verified against
        a hook specification are optional, otherwise raise PluginValidationError"""
        for name in self.hook.__dict__:
            if name[0] != "_":
                hook = getattr(self.hook, name)  # type: _HookCaller
                if not hook.has_spec():
                    for hookimpl in hook.get_hookimpls():
                        if not hookimpl.optionalhook:
                            raise PluginValidationError(
                                hookimpl.plugin,
                                "unknown hook %r in plugin %r"
                                % (name, hookimpl.plugin),
                            )

    def load_setuptools_entrypoints(self, group, name=None):
        # type: (str, Optional[str]) -> int
        """ Load modules from querying the specified setuptools ``group``.

        :param str group: entry point group to load plugins
        :param str name: if given, loads only plugins with the given ``name``.
        :rtype: int
        :return: return the number of loaded plugins by this call.
        """
        count = 0
        # Types ignored because importlib.metadata doesn't have stubs yet.
        for dist in metadata.distributions():
            for ep in dist.entry_points:
                if (
                    ep.group != group
                    or (name is not None and ep.name != name)
                    # already registered
                    or self.get_plugin(ep.name)
                    or self.is_blocked(ep.name)
                ):
                    continue
                plugin = ep.load()
                self.register(plugin, name=ep.name)
                self._plugin_distinfo.append((plugin, DistFacade(dist)))  # type: ignore
                count += 1
        return count

    def list_plugin_distinfo(self):
        # type: () -> List[Tuple[_Plugin, DistFacade]]
        """ return list of distinfo/plugin tuples for all setuptools registered
        plugins. """
        return list(self._plugin_distinfo)

    def list_name_plugin(self):
        # type: () -> List[Tuple[str, _Plugin]]
        """ return list of name/plugin pairs. """
        return list(self._name2plugin.items())

    def get_hookcallers(self, plugin):
        # type: (_Plugin) -> Optional[List[_HookCaller]]
        """ get all hook callers for the specified plugin. """
        return self._plugin2hookcallers.get(plugin)

    def add_hookcall_monitoring(self, before, after):
        # type: (_tracing._BeforeTrace, _tracing._AfterTrace) -> Callable[[], None]
        """ add before/after tracing functions for all hooks
        and return an undo function which, when called,
        will remove the added tracers.

        ``before(hook_name, hook_impls, kwargs)`` will be called ahead
        of all hook calls and receive a hookcaller instance, a list
        of HookImpl instances and the keyword arguments for the hook call.

        ``after(outcome, hook_name, hook_impls, kwargs)`` receives the
        same arguments as ``before`` but also a :py:class:`_Result`` object
        which represents the result of the overall hook call.
        """
        return _tracing._TracedHookExecution(self, before, after).undo

    def enable_tracing(self):
        # type: () -> Callable[[], None]
        """ enable tracing of hook calls and return an undo function. """
        hooktrace = self.hook._trace

        def before(hook_name, methods, kwargs):
            # type: (str, List[HookImpl], Dict[str, object]) -> None
            hooktrace.root.indent += 1
            hooktrace(hook_name, kwargs)

        def after(outcome, hook_name, methods, kwargs):
            # type: (_Result[object], str, List[HookImpl], Dict[str, object]) -> None
            if outcome.excinfo is None:
                hooktrace("finish", hook_name, "-->", outcome.get_result())
            hooktrace.root.indent -= 1

        return self.add_hookcall_monitoring(before, after)

    def subset_hook_caller(self, name, remove_plugins):
        # type: (str, Iterable[_Plugin]) -> _HookCaller
        """ Return a new _HookCaller instance for the named method
        which manages calls to all registered plugins except the
        ones from remove_plugins. """
        orig = getattr(self.hook, name)  # type: _HookCaller
        plugins_to_remove = [plug for plug in remove_plugins if hasattr(plug, name)]
        if plugins_to_remove:
            assert orig.spec is not None
            hc = _HookCaller(
                orig.name, orig._hookexec, orig.spec.namespace, orig.spec.opts
            )
            for hookimpl in orig.get_hookimpls():
                plugin = hookimpl.plugin
                if plugin not in plugins_to_remove:
                    hc._add_hookimpl(hookimpl)
                    # we also keep track of this hook caller so it
                    # gets properly removed on plugin unregistration
                    self._plugin2hookcallers.setdefault(plugin, []).append(hc)
            return hc
        return orig


def _formatdef(func):
    # type: (Callable[..., object]) -> str
    if hasattr(inspect, "signature"):
        sig = str(inspect.signature(func))
    else:
        sig = inspect.formatargspec(*inspect.getargspec(func))
    return "%s%s" % (func.__name__, sig)
