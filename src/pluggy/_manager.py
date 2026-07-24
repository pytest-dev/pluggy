from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
import inspect
import types
from typing import Any
from typing import cast
from typing import Final
from typing import TYPE_CHECKING
from typing import TypeAlias
import warnings

from . import _tracing
from ._callers import _multicall
from ._config import hookimpl_config_from_mapping
from ._config import hookimpl_config_to_mapping
from ._config import HookimplConfiguration
from ._config import hookspec_config_from_mapping
from ._config import hookspec_config_to_mapping
from ._config import HookspecConfiguration
from ._hooks import _HookImplFunction
from ._hooks import _Namespace
from ._hooks import _Plugin
from ._hooks import HistoricHookCaller
from ._hooks import HookCaller
from ._hooks import HookImpl
from ._hooks import HookRelay
from ._hooks import NormalHookCaller
from ._hooks import NormalImpl
from ._hooks import SubsetHookCaller
from ._hooks import WrapperImpl
from ._project import ProjectSpec
from ._pytest_compat import HookimplOpts
from ._pytest_compat import HookspecOpts
from ._result import Result


if TYPE_CHECKING:
    import importlib.metadata

    from ._compat import DistFacade


_BeforeTrace: TypeAlias = Callable[[str, Sequence[HookImpl], Mapping[str, Any]], None]
_AfterTrace: TypeAlias = Callable[
    [Result[Any], str, Sequence[HookImpl], Mapping[str, Any]], None
]


def _warn_for_function(warning: Warning, function: Callable[..., object]) -> None:
    func = cast(types.FunctionType, function)
    warnings.warn_explicit(
        warning,
        type(warning),
        lineno=func.__code__.co_firstlineno,
        filename=func.__code__.co_filename,
    )


class PluginValidationError(Exception):
    """Plugin failed validation.

    :param plugin: The plugin which failed validation.
    :param message: Error message.
    """

    def __init__(self, plugin: _Plugin, message: str) -> None:
        super().__init__(message)
        #: The plugin which failed validation.
        self.plugin = plugin


class PluginManager:
    """Core class which manages registration of plugin objects and 1:N hook
    calling.

    You can register new hooks by calling :meth:`add_hookspecs(module_or_class)
    <PluginManager.add_hookspecs>`.

    You can register plugin objects (which contain hook implementations) by
    calling :meth:`register(plugin) <PluginManager.register>`.

    For debugging purposes you can call :meth:`PluginManager.enable_tracing`
    which will subsequently send debug information to the trace helper.

    :param project_name:
        The short project name (prefer snake case, make sure it's unique!),
        or a :class:`ProjectSpec` instance.

    .. versionchanged:: 1.7
        A :class:`ProjectSpec` may be passed instead of a plain name.
    """

    def __init__(self, project_name: str | ProjectSpec) -> None:
        self._project_spec: Final = (
            ProjectSpec(project_name) if isinstance(project_name, str) else project_name
        )
        self._name2plugin: Final[dict[str, _Plugin]] = {}
        self._plugin_distinfo: Final[
            list[tuple[_Plugin, importlib.metadata.Distribution]]
        ] = []
        #: The "hook relay", used to call a hook on all registered plugins.
        #: See :ref:`calling`.
        self.hook: Final = HookRelay()
        #: The tracing entry point. See :ref:`tracing`.
        self.trace: Final[_tracing.TagTracerSub] = _tracing.TagTracer().get(
            "pluginmanage"
        )
        self._inner_hookexec = _multicall

    @property
    def project_name(self) -> str:
        """The project name from the associated :class:`ProjectSpec`."""
        return self._project_spec.project_name

    def _hookexec(
        self,
        hook_name: str,
        normal_impls: Sequence[NormalImpl],
        wrapper_impls: Sequence[WrapperImpl],
        caller_kwargs: Mapping[str, object],
        firstresult: bool,
    ) -> object | list[object]:
        # called from all hookcaller instances.
        # enable_tracing will set its own wrapping function at self._inner_hookexec
        return self._inner_hookexec(
            hook_name, normal_impls, wrapper_impls, caller_kwargs, firstresult
        )

    def register(self, plugin: _Plugin, name: str | None = None) -> str | None:
        """Register a plugin and return its name.

        :param name:
            The name under which to register the plugin. If not specified, a
            name is generated using :func:`get_canonical_name`.

        :returns:
            The plugin name. If the name is blocked from registering, returns
            ``None``.

        If the plugin is already registered, raises a :exc:`ValueError`.
        """
        plugin_name = name or self.get_canonical_name(plugin)

        if plugin_name in self._name2plugin:
            if self._name2plugin.get(plugin_name, -1) is None:
                return None  # blocked plugin, return None to indicate no registration
            raise ValueError(
                "Plugin name already registered: "
                f"{plugin_name}={plugin}\n{self._name2plugin}"
            )

        if plugin in self._name2plugin.values():
            raise ValueError(
                "Plugin already registered under a different name: "
                f"{plugin_name}={plugin}\n{self._name2plugin}"
            )

        # XXX if an error happens we should make sure no state has been
        # changed at point of return
        self._name2plugin[plugin_name] = plugin

        # register matching hook implementations of the plugin
        for name in dir(plugin):
            hookimpl_config = self._discover_hookimpl_configuration(plugin, name)
            if hookimpl_config is not None:
                method: _HookImplFunction[object] = getattr(plugin, name)
                hookimpl = hookimpl_config.create_hookimpl(plugin, plugin_name, method)
                hook_name = hookimpl_config.specname or name
                hook: NormalHookCaller | HistoricHookCaller | None = getattr(
                    self.hook, hook_name, None
                )
                if hook is None:
                    hook = NormalHookCaller(hook_name, self._hookexec)
                    setattr(self.hook, hook_name, hook)
                elif hook.has_spec():
                    self._verify_hook(hook, hookimpl)
                    hook._maybe_apply_history(hookimpl)
                hook._add_hookimpl(hookimpl)
        return plugin_name

    def _read_hookimpl_configuration(
        self, plugin: _Plugin, name: str
    ) -> HookimplConfiguration | None:
        """Read a modern :class:`HookimplConfiguration` from a plugin attribute."""
        try:
            method: object = getattr(plugin, name)
        except Exception:
            # dir() can include properties that are not safely readable yet
            # (e.g. pytest Config during early registration).
            return None
        if not inspect.isroutine(method):
            return None
        try:
            res: object = getattr(method, self.project_name + "_impl", None)
        except Exception:  # pragma: no cover
            return None
        if isinstance(res, HookimplConfiguration):
            return res
        if isinstance(res, Mapping):
            return hookimpl_config_from_mapping(res)
        return None

    def _discover_hookimpl_configuration(
        self, plugin: _Plugin, name: str
    ) -> HookimplConfiguration | None:
        """Discover hookimpl configuration for registration.

        Prefer the modern marker attribute. Only call the deprecated
        :meth:`parse_hookimpl_opts` when a subclass actually overrides it and
        no modern configuration was found (pytest unmarked-hook concession).
        """
        config = self._read_hookimpl_configuration(plugin, name)
        if config is not None:
            return config
        parse_hookimpl_opts = type(self).parse_hookimpl_opts
        if parse_hookimpl_opts is PluginManager.parse_hookimpl_opts:
            return None
        legacy = parse_hookimpl_opts(self, plugin, name)
        if legacy is None:
            return None
        return hookimpl_config_from_mapping(legacy)

    def parse_hookimpl_opts(self, plugin: _Plugin, name: str) -> HookimplOpts | None:
        """Return legacy dict-shaped hookimpl options, if any.

        .. deprecated::
            Thin pytest/support concession. Registration uses private discovery
            of :class:`HookimplConfiguration` and only invokes this method when
            a subclass overrides it and no modern configuration attribute was
            found. Prefer marker-attached configuration objects.
        """
        config = self._read_hookimpl_configuration(plugin, name)
        if config is None:
            return None
        return cast(HookimplOpts, hookimpl_config_to_mapping(config))

    def unregister(
        self, plugin: _Plugin | None = None, name: str | None = None
    ) -> Any | None:
        """Unregister a plugin and all of its hook implementations.

        The plugin can be specified either by the plugin object or the plugin
        name. If both are specified, they must agree.

        Returns the unregistered plugin, or ``None`` if not found.
        """
        if name is None:
            assert plugin is not None, "one of name or plugin needs to be specified"
            name = self.get_name(plugin)
            assert name is not None, "plugin is not registered"

        if plugin is None:
            plugin = self.get_plugin(name)
            if plugin is None:
                return None

        hookcallers = self.get_hookcallers(plugin)
        if hookcallers:
            for hookcaller in hookcallers:
                assert isinstance(hookcaller, (NormalHookCaller, HistoricHookCaller))
                hookcaller._remove_plugin(plugin)

        # if self._name2plugin[name] == None registration was blocked: ignore
        if self._name2plugin.get(name):
            assert name is not None
            del self._name2plugin[name]

        return plugin

    def set_blocked(self, name: str) -> None:
        """Block registrations of the given name, unregister if already registered."""
        self.unregister(name=name)
        self._name2plugin[name] = None

    def is_blocked(self, name: str) -> bool:
        """Return whether the given plugin name is blocked."""
        return name in self._name2plugin and self._name2plugin[name] is None

    def unblock(self, name: str) -> bool:
        """Unblocks a name.

        Returns whether the name was actually blocked.
        """
        if self._name2plugin.get(name, -1) is None:
            del self._name2plugin[name]
            return True
        return False

    def add_hookspecs(self, module_or_class: _Namespace) -> None:
        """Add new hook specifications defined in the given ``module_or_class``.

        Functions are recognized as hook specifications if they have been
        decorated with a matching :class:`HookspecMarker`.
        """
        names = []
        for name in dir(module_or_class):
            spec_config = self._discover_hookspec_configuration(module_or_class, name)
            if spec_config is not None:
                hc: NormalHookCaller | HistoricHookCaller | None = getattr(
                    self.hook, name, None
                )
                if hc is None:
                    if spec_config.historic:
                        hc = HistoricHookCaller(
                            name, self._hookexec, module_or_class, spec_config
                        )
                    else:
                        hc = NormalHookCaller(
                            name, self._hookexec, module_or_class, spec_config
                        )
                    setattr(self.hook, name, hc)
                elif spec_config.historic and not hc.is_historic():
                    # Plugins registered this hook before the historic spec was
                    # known - hand the implementations over to a
                    # HistoricHookCaller.
                    assert isinstance(hc, NormalHookCaller)
                    if hc.has_spec():
                        # Let set_specification raise the usual error.
                        hc.set_specification(module_or_class, spec_config)
                        raise AssertionError("unreachable")  # pragma: no cover
                    old_hookimpls = hc.get_hookimpls()
                    historic_hc = HistoricHookCaller(
                        name, self._hookexec, module_or_class, spec_config
                    )
                    setattr(self.hook, name, historic_hc)
                    for hookimpl in old_hookimpls:
                        self._verify_hook(historic_hc, hookimpl)
                        historic_hc._add_hookimpl(hookimpl)
                else:
                    # Plugins registered this hook without knowing the spec.
                    hc.set_specification(module_or_class, spec_config)
                    for hookfunction in hc.get_hookimpls():
                        self._verify_hook(hc, hookfunction)
                names.append(name)

        if not names:
            raise ValueError(
                f"did not find any {self.project_name!r} hooks in {module_or_class!r}"
            )

    def _read_hookspec_configuration(
        self, module_or_class: _Namespace, name: str
    ) -> HookspecConfiguration | None:
        """Read a modern :class:`HookspecConfiguration` from a marked function."""
        try:
            method = getattr(module_or_class, name)
        except Exception:
            return None
        try:
            opts: object = getattr(method, self.project_name + "_spec", None)
        except Exception:  # pragma: no cover
            return None
        if isinstance(opts, HookspecConfiguration):
            return opts
        if isinstance(opts, Mapping):
            return hookspec_config_from_mapping(opts)
        return None

    def _discover_hookspec_configuration(
        self, module_or_class: _Namespace, name: str
    ) -> HookspecConfiguration | None:
        """Discover hookspec configuration for ``add_hookspecs``.

        Prefer the modern marker attribute. Only call the deprecated
        :meth:`parse_hookspec_opts` when a subclass actually overrides it and
        no modern configuration was found.
        """
        config = self._read_hookspec_configuration(module_or_class, name)
        if config is not None:
            return config
        parse_hookspec_opts = type(self).parse_hookspec_opts
        if parse_hookspec_opts is PluginManager.parse_hookspec_opts:
            return None
        legacy = parse_hookspec_opts(self, module_or_class, name)
        if legacy is None:
            return None
        return hookspec_config_from_mapping(legacy)

    def parse_hookspec_opts(
        self, module_or_class: _Namespace, name: str
    ) -> HookspecOpts | None:
        """Return legacy dict-shaped hookspec options, if any.

        .. deprecated::
            Thin pytest/support concession. ``add_hookspecs`` uses private
            discovery of :class:`HookspecConfiguration` and only invokes this
            method when a subclass overrides it and no modern configuration
            attribute was found. Prefer marker-attached configuration objects.
        """
        config = self._read_hookspec_configuration(module_or_class, name)
        if config is None:
            return None
        return cast(HookspecOpts, hookspec_config_to_mapping(config))

    def get_plugins(self) -> set[Any]:
        """Return a set of all registered plugin objects."""
        return {x for x in self._name2plugin.values() if x is not None}

    def is_registered(self, plugin: _Plugin) -> bool:
        """Return whether the plugin is already registered."""
        return any(plugin == val for val in self._name2plugin.values())

    def get_canonical_name(self, plugin: _Plugin) -> str:
        """Return a canonical name for a plugin object.

        Note that a plugin may be registered under a different name
        specified by the caller of :meth:`register(plugin, name) <register>`.
        To obtain the name of a registered plugin use :meth:`get_name(plugin)
        <get_name>` instead.
        """
        name: str | None = getattr(plugin, "__name__", None)
        return name or str(id(plugin))

    def get_plugin(self, name: str) -> Any | None:
        """Return the plugin registered under the given name, if any."""
        return self._name2plugin.get(name)

    def has_plugin(self, name: str) -> bool:
        """Return whether a plugin with the given name is registered."""
        return self.get_plugin(name) is not None

    def get_name(self, plugin: _Plugin) -> str | None:
        """Return the name the plugin is registered under, or ``None`` if
        is isn't."""
        for name, val in self._name2plugin.items():
            if plugin == val:
                return name
        return None

    def _verify_hook(self, hook: HookCaller, hookimpl: HookImpl) -> None:
        if hook.is_historic() and (hookimpl.hookwrapper or hookimpl.wrapper):
            raise PluginValidationError(
                hookimpl.plugin,
                f"Plugin {hookimpl.plugin_name!r}\nhook {hook.name!r}\n"
                "historic incompatible with yield/wrapper/hookwrapper",
            )

        assert hook.spec is not None
        if hook.spec.warn_on_impl:
            _warn_for_function(hook.spec.warn_on_impl, hookimpl.function)

        # positional arg checking
        notinspec = set(hookimpl.argnames) - set(hook.spec.argnames)
        if notinspec:
            raise PluginValidationError(
                hookimpl.plugin,
                f"Plugin {hookimpl.plugin_name!r} for hook {hook.name!r}\n"
                f"hookimpl definition: {_formatdef(hookimpl.function)}\n"
                f"Argument(s) {notinspec} are declared in the hookimpl but "
                "can not be found in the hookspec",
            )

        if hook.spec.warn_on_impl_args:
            for hookimpl_argname in hookimpl.argnames:
                argname_warning = hook.spec.warn_on_impl_args.get(hookimpl_argname)
                if argname_warning is not None:
                    _warn_for_function(argname_warning, hookimpl.function)

        if (
            hookimpl.wrapper or hookimpl.hookwrapper
        ) and not inspect.isgeneratorfunction(hookimpl.function):
            raise PluginValidationError(
                hookimpl.plugin,
                f"Plugin {hookimpl.plugin_name!r} for hook {hook.name!r}\n"
                f"hookimpl definition: {_formatdef(hookimpl.function)}\n"
                "Declared as wrapper=True or hookwrapper=True "
                "but function is not a generator function",
            )

        if hookimpl.wrapper and hookimpl.hookwrapper:
            raise PluginValidationError(
                hookimpl.plugin,
                f"Plugin {hookimpl.plugin_name!r} for hook {hook.name!r}\n"
                f"hookimpl definition: {_formatdef(hookimpl.function)}\n"
                "The wrapper=True and hookwrapper=True options are mutually exclusive",
            )

    def check_pending(self) -> None:
        """Verify that all hooks which have not been verified against a
        hook specification are optional, otherwise raise
        :exc:`PluginValidationError`."""
        for name in self.hook.__dict__:
            if name[0] == "_":
                continue
            hook: NormalHookCaller | HistoricHookCaller = getattr(self.hook, name)
            if not hook.has_spec():
                for hookimpl in hook.get_hookimpls():
                    if not hookimpl.optionalhook:
                        raise PluginValidationError(
                            hookimpl.plugin,
                            f"unknown hook {name!r} in plugin {hookimpl.plugin!r}",
                        )

    def load_setuptools_entrypoints(self, group: str, name: str | None = None) -> int:
        """Load modules from querying the specified setuptools ``group``.

        :param group:
            Entry point group to load plugins.
        :param name:
            If given, loads only plugins with the given ``name``.

        :return:
            The number of plugins loaded by this call.
        """
        import importlib.metadata

        count = 0
        for dist in list(importlib.metadata.distributions()):
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
                self._plugin_distinfo.append((plugin, dist))
                count += 1
        return count

    def list_plugin_distinfo(self) -> list[tuple[_Plugin, DistFacade]]:
        """Return a list of (plugin, distinfo) pairs for all
        setuptools-registered plugins.

        .. note::
            The distinfo objects are wrapped with :class:`~pluggy._compat.DistFacade`
            for backward compatibility with the legacy pkg_resources API.
            Prefer :meth:`list_plugin_distributions` for raw
            :class:`importlib.metadata.Distribution` objects.
        """
        from ._compat import DistFacade

        return [(plugin, DistFacade(dist)) for plugin, dist in self._plugin_distinfo]

    def list_plugin_distributions(
        self,
    ) -> list[tuple[_Plugin, importlib.metadata.Distribution]]:
        """Return a list of (plugin, distribution) pairs for all plugins
        loaded via entry points.

        .. versionadded:: 1.7
        """
        return list(self._plugin_distinfo)

    def list_name_plugin(self) -> list[tuple[str, _Plugin]]:
        """Return a list of (name, plugin) pairs for all registered plugins."""
        return list(self._name2plugin.items())

    def get_hookcallers(self, plugin: _Plugin) -> list[HookCaller] | None:
        """Get all hook callers for the specified plugin.

        :returns:
            The hook callers, or ``None`` if ``plugin`` is not registered in
            this plugin manager.
        """
        if self.get_name(plugin) is None:
            return None
        hookcallers = []
        for hookcaller in self.hook.__dict__.values():
            if any(impl.plugin is plugin for impl in hookcaller.get_hookimpls()):
                hookcallers.append(hookcaller)
        return hookcallers

    def add_hookcall_monitoring(
        self, before: _BeforeTrace, after: _AfterTrace
    ) -> Callable[[], None]:
        """Add before/after tracing functions for all hooks.

        Returns an undo function which, when called, removes the added tracers.

        ``before(hook_name, hook_impls, kwargs)`` will be called ahead
        of all hook calls and receive a hookcaller instance, a list
        of HookImpl instances and the keyword arguments for the hook call.

        ``after(outcome, hook_name, hook_impls, kwargs)`` receives the
        same arguments as ``before`` but also a :class:`~pluggy.Result` object
        which represents the result of the overall hook call.
        """
        oldcall = self._inner_hookexec

        def traced_hookexec(
            hook_name: str,
            normal_impls: Sequence[NormalImpl],
            wrapper_impls: Sequence[WrapperImpl],
            caller_kwargs: Mapping[str, object],
            firstresult: bool,
        ) -> object | list[object]:
            # For backward compatibility of the before/after callback shapes,
            # combine the split lists into one.
            hook_impls: list[HookImpl] = [*normal_impls, *wrapper_impls]
            before(hook_name, hook_impls, caller_kwargs)
            outcome = Result.from_call(
                lambda: oldcall(
                    hook_name, normal_impls, wrapper_impls, caller_kwargs, firstresult
                )
            )
            after(outcome, hook_name, hook_impls, caller_kwargs)
            return outcome.get_result()

        self._inner_hookexec = traced_hookexec

        def undo() -> None:
            self._inner_hookexec = oldcall

        return undo

    def enable_tracing(self) -> Callable[[], None]:
        """Enable tracing of hook calls.

        Returns an undo function which, when called, removes the added tracing.
        """
        hooktrace = self.trace.root.get("hook")

        def before(
            hook_name: str, methods: Sequence[HookImpl], kwargs: Mapping[str, object]
        ) -> None:
            hooktrace.root.indent += 1
            hooktrace(hook_name, kwargs)

        def after(
            outcome: Result[object],
            hook_name: str,
            methods: Sequence[HookImpl],
            kwargs: Mapping[str, object],
        ) -> None:
            if outcome.exception is None:
                hooktrace("finish", hook_name, "-->", outcome.get_result())
            hooktrace.root.indent -= 1

        return self.add_hookcall_monitoring(before, after)

    def subset_hook_caller(
        self, name: str, remove_plugins: Iterable[_Plugin]
    ) -> HookCaller:
        """Return a proxy :class:`~pluggy.HookCaller` instance for the named
        method which manages calls to all registered plugins except the ones
        from remove_plugins."""
        orig: NormalHookCaller | HistoricHookCaller = getattr(self.hook, name)
        plugins_to_remove = {plug for plug in remove_plugins if hasattr(plug, name)}
        if plugins_to_remove:
            return SubsetHookCaller(orig, plugins_to_remove)
        return orig


def _formatdef(func: Callable[..., object]) -> str:
    return f"{func.__name__}{inspect.signature(func)}"
