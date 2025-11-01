from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
import inspect
import types
from typing import Any
from typing import Callable
from typing import cast
from typing import Final
from typing import TYPE_CHECKING
from typing import TypeVar
import warnings

from . import _project
from . import _tracing
from ._async import Submitter
from ._callers import _multicall
from ._hook_callers import HistoricHookCaller
from ._hook_callers import HookCaller
from ._hook_callers import HookImpl
from ._hook_callers import HookRelay
from ._hook_callers import NormalHookCaller
from ._hook_callers import SubsetHookCaller
from ._hook_callers import WrapperImpl
from ._hook_config import _HookImplFunction
from ._hook_config import _Namespace
from ._hook_config import _Plugin
from ._hook_config import HookimplConfiguration
from ._hook_config import HookimplOpts
from ._hook_config import HookspecConfiguration
from ._hook_config import HookspecOpts
from ._result import Result


if TYPE_CHECKING:
    # importtlib.metadata import is slow, defer it.
    import importlib.metadata


_T = TypeVar("_T")
_BeforeTrace = Callable[[str, Sequence[HookImpl], Mapping[str, Any]], None]
_AfterTrace = Callable[[Result[Any], str, Sequence[HookImpl], Mapping[str, Any]], None]


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


class DistFacade:
    """Emulate a pkg_resources Distribution"""

    def __init__(self, dist: importlib.metadata.Distribution) -> None:
        self._dist = dist

    @property
    def project_name(self) -> str:
        name: str = self.metadata["name"]
        return name

    def __getattr__(self, attr: str, default: Any | None = None) -> Any:
        return getattr(self._dist, attr, default)

    def __dir__(self) -> list[str]:
        return sorted(dir(self._dist) + ["_dist", "project_name"])


class PluginManager:
    """Core class which manages registration of plugin objects and 1:N hook
    calling.

    You can register new hooks by calling :meth:`add_hookspecs(module_or_class)
    <PluginManager.add_hookspecs>`.

    You can register plugin objects (which contain hook implementations) by
    calling :meth:`register(plugin) <PluginManager.register>`.

    For debugging purposes you can call :meth:`PluginManager.enable_tracing`
    which will subsequently send debug information to the trace helper.

    :param project_name_or_spec:
        The short project name (string) or a ProjectSpec instance.
    """

    def __init__(
        self,
        project_name_or_spec: str | _project.ProjectSpec,
        async_submitter: Submitter | None = None,
    ) -> None:
        self._project_spec: Final = (
            _project.ProjectSpec(project_name_or_spec)
            if isinstance(project_name_or_spec, str)
            else project_name_or_spec
        )

        self._name2plugin: Final[dict[str, _Plugin]] = {}
        self._plugin_distinfo: Final[list[tuple[_Plugin, DistFacade]]] = []
        #: The "hook relay", used to call a hook on all registered plugins.
        #: See :ref:`calling`.
        self.hook: Final = HookRelay()
        #: The tracing entry point. See :ref:`tracing`.
        self.trace: Final[_tracing.TagTracerSub] = _tracing.TagTracer().get(
            "pluginmanage"
        )
        self._inner_hookexec = _multicall
        self._async_submitter: Submitter = async_submitter or Submitter()

    @property
    def project_name(self) -> str:
        """The project name from the associated ProjectSpec."""
        return self._project_spec.project_name

    def _hookexec(
        self,
        hook_name: str,
        normal_impls: Sequence[HookImpl],
        wrapper_impls: Sequence[WrapperImpl],
        caller_kwargs: Mapping[str, object],
        firstresult: bool,
        async_submitter: Submitter,
    ) -> object | list[object]:
        # called from all hookcaller instances.
        # enable_tracing will set its own wrapping function at self._inner_hookexec
        return self._inner_hookexec(
            hook_name,
            normal_impls,
            wrapper_impls,
            caller_kwargs,
            firstresult,
            async_submitter,
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
            hookimpl_config = self._parse_hookimpl(plugin, name)
            if hookimpl_config is not None:
                method: _HookImplFunction[object] = getattr(plugin, name)
                hookimpl = hookimpl_config.create_hookimpl(plugin, plugin_name, method)
                hook_name = hookimpl_config.specname or name
                hook: NormalHookCaller | HistoricHookCaller | None = getattr(
                    self.hook, hook_name, None
                )
                if hook is None:
                    hook = NormalHookCaller(
                        hook_name, self._hookexec, self._async_submitter
                    )
                    setattr(self.hook, hook_name, hook)
                elif hook.has_spec():
                    self._verify_hook(hook, hookimpl)
                # With stronger types, we can access _add_hookimpl directly
                # Historic hooks only accept HookImpl, not WrapperImpl
                if hook.is_historic():
                    if isinstance(hookimpl, WrapperImpl):
                        raise PluginValidationError(
                            hookimpl.plugin,
                            f"Plugin {hookimpl.plugin_name!r}\nhook {hook_name!r}\n"
                            "Historic hooks do not support wrappers.",
                        )
                    # hook is HistoricHookCaller here
                    # We already checked that hookimpl is not WrapperImpl above
                    assert isinstance(hookimpl, HookImpl)
                    hook._add_hookimpl(hookimpl)
                else:
                    # hook is NormalHookCaller here
                    assert isinstance(hook, NormalHookCaller)
                    hook._add_hookimpl(hookimpl)
        return plugin_name

    def _parse_hookimpl(
        self, plugin: _Plugin, name: str
    ) -> HookimplConfiguration | None:
        """Internal method to parse hook implementation configuration.

        :param plugin: The plugin object to inspect
        :param name: The attribute name to check for hook implementation
        :returns: HookimplConfiguration if found, None otherwise
        """
        try:
            method: object = getattr(plugin, name)
        except Exception:  # pragma: no cover
            return None

        if not inspect.isroutine(method):
            return None

        # Get hook implementation configuration using ProjectSpec
        impl_config = self._project_spec.get_hookimpl_config(method)
        if impl_config is not None:
            return impl_config

        # Fall back to legacy parse_hookimpl_opts for compatibility
        # (e.g. pytest override)
        legacy_opts = self.parse_hookimpl_opts(plugin, name)
        if legacy_opts is not None:
            return HookimplConfiguration(**legacy_opts)

        return None

    def _parse_hookspec(
        self, module_or_class: _Namespace, name: str
    ) -> HookspecConfiguration | None:
        """Internal method to parse hook specification configuration.

        :param module_or_class: The module or class to inspect
        :param name: The attribute name to check for hook specification
        :returns: HookspecConfiguration if found, None otherwise
        """
        try:
            method: object = getattr(module_or_class, name)
        except Exception:  # pragma: no cover
            return None

        if not inspect.isroutine(method):
            return None

        # Get hook specification configuration using ProjectSpec
        spec_config = self._project_spec.get_hookspec_config(method)
        if spec_config is not None:
            return spec_config

        # Fall back to legacy parse_hookspec_opts for compatibility
        legacy_opts = self.parse_hookspec_opts(module_or_class, name)
        if legacy_opts is not None:
            return HookspecConfiguration(**legacy_opts)

        return None

    def parse_hookimpl_opts(self, plugin: _Plugin, name: str) -> HookimplOpts | None:
        """Try to obtain a hook implementation from an item with the given name
        in the given plugin which is being searched for hook impls.

        :returns:
            The parsed hookimpl options, or None to skip the given item.

        .. deprecated::
            Customizing hook implementation parsing by overriding this method is
            deprecated. This method is only kept as a compatibility shim for
            legacy projects like pytest. New code should use the standard
            :class:`HookimplMarker` decorators.
        """
        # Compatibility shim - only overridden by legacy projects like pytest
        # Modern hook implementations are handled by _parse_hookimpl
        return None

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
                # hookcaller is typed as Union[NormalHookCaller, HistoricHookCaller]
                concrete_hook = hookcaller
                concrete_hook._remove_plugin(plugin)

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
            spec_config = self._parse_hookspec(module_or_class, name)
            if spec_config is not None:
                hc: NormalHookCaller | HistoricHookCaller | None = getattr(
                    self.hook, name, None
                )
                if hc is None:
                    if spec_config.historic:
                        hc = HistoricHookCaller(
                            name,
                            self._hookexec,
                            module_or_class,
                            spec_config,
                            self._async_submitter,
                        )
                    else:
                        hc = NormalHookCaller(
                            name,
                            self._hookexec,
                            self._async_submitter,
                            module_or_class,
                            spec_config,
                        )
                    setattr(self.hook, name, hc)
                else:
                    # Plugins registered this hook without knowing the spec.
                    if spec_config.historic and isinstance(hc, NormalHookCaller):
                        # Need to handover from HookCaller to HistoricHookCaller
                        old_hookimpls = hc.get_hookimpls()
                        hc = HistoricHookCaller(
                            name,
                            self._hookexec,
                            module_or_class,
                            spec_config,
                            self._async_submitter,
                        )
                        # Re-add existing hookimpls (history applied by _add_hookimpl)
                        # Only normal implementations can be moved to historic hooks
                        for hookimpl in old_hookimpls:
                            if hookimpl.hookwrapper or hookimpl.wrapper:
                                raise PluginValidationError(
                                    hookimpl.plugin,
                                    f"Plugin {hookimpl.plugin_name!r}\nhook {name!r}\n"
                                    "Historic hooks do not support wrappers.",
                                )
                            # hc is HistoricHookCaller, access _add_hookimpl directly
                            hc._add_hookimpl(hookimpl)
                        setattr(self.hook, name, hc)
                    else:
                        hc.set_specification(module_or_class, spec_config)
                    for hookfunction in hc.get_hookimpls():
                        # hookfunction is now already typed as HookImpl
                        self._verify_hook(hc, hookfunction)
                names.append(name)

        if not names:
            raise ValueError(
                f"did not find any {self.project_name!r} hooks in {module_or_class!r}"
            )

    def parse_hookspec_opts(
        self, module_or_class: _Namespace, name: str
    ) -> HookspecOpts | None:
        """Try to obtain a hook specification from an item with the given name
        in the given module or class which is being searched for hook specs.

        :returns:
            The parsed hookspec options for defining a hook, or None to skip the
            given item.

        .. deprecated::
            Customizing hook specification parsing by overriding this method is
            deprecated. This method is only kept as a compatibility shim for
            legacy projects. New code should use the standard
            :class:`HookspecMarker` decorators.
        """
        # Compatibility shim - only overridden by legacy projects
        # Modern hook specifications are handled by _parse_hookspec
        return None

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

    def _verify_hook(
        self,
        hook: NormalHookCaller | HistoricHookCaller,
        hookimpl: HookImpl | WrapperImpl,
    ) -> None:
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
                self._plugin_distinfo.append((plugin, DistFacade(dist)))
                count += 1
        return count

    def list_plugin_distinfo(self) -> list[tuple[_Plugin, DistFacade]]:
        """Return a list of (plugin, distinfo) pairs for all
        setuptools-registered plugins."""
        return list(self._plugin_distinfo)

    def list_name_plugin(self) -> list[tuple[str, _Plugin]]:
        """Return a list of (name, plugin) pairs for all registered plugins."""
        return list(self._name2plugin.items())

    def get_hookcallers(
        self, plugin: _Plugin
    ) -> list[NormalHookCaller | HistoricHookCaller] | None:
        """Get all hook callers for the specified plugin.

        :returns:
            The hook callers, or ``None`` if ``plugin`` is not registered in
            this plugin manager.
        """
        if self.get_name(plugin) is None:
            return None
        hookcallers: list[NormalHookCaller | HistoricHookCaller] = []
        for hookcaller in self.hook.__dict__.values():
            for hookimpl in hookcaller.get_hookimpls():
                if hookimpl.plugin is plugin:
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
            normal_impls: Sequence[HookImpl],
            wrapper_impls: Sequence[WrapperImpl],
            caller_kwargs: Mapping[str, object],
            firstresult: bool,
            async_submitter: Submitter,
        ) -> object | list[object]:
            # For backward compatibility, combine the lists for tracing callbacks
            combined_hook_impls = [*normal_impls, *wrapper_impls]
            before(hook_name, combined_hook_impls, caller_kwargs)
            outcome = Result.from_call(
                lambda: oldcall(
                    hook_name,
                    normal_impls,
                    wrapper_impls,
                    caller_kwargs,
                    firstresult,
                    self._async_submitter,
                )
            )
            after(outcome, hook_name, combined_hook_impls, caller_kwargs)
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
        # Return as HookCaller protocol for compatibility
        return cast(HookCaller, orig)

    async def run_async(self, func: Callable[[], _T]) -> _T:
        """Run a function with async support enabled for hook results.

        This method runs the provided function in a greenlet context that enables
        awaiting async results returned by hooks. Hook results that are awaitable
        will be automatically awaited when running in this context.

        :param func: The function to run with async support enabled
        :returns: The result of the function
        :raises RuntimeError: If greenlet is not available

        Example:
            pm = PluginManager("myapp")
            result = await pm.run_async(lambda: pm.hook.some_hook())
        """

        def wrapper() -> _T:
            # Store the async submitter in the plugin manager for hook execution
            old_hookexec = self._inner_hookexec

            def async_hookexec(
                hook_name: str,
                normal_impls: Sequence[HookImpl],
                wrapper_impls: Sequence[WrapperImpl],
                caller_kwargs: Mapping[str, object],
                firstresult: bool,
                async_submitter: Submitter,
            ) -> object | list[object]:
                return old_hookexec(
                    hook_name,
                    normal_impls,
                    wrapper_impls,
                    caller_kwargs,
                    firstresult,
                    async_submitter,
                )

            try:
                self._inner_hookexec = async_hookexec
                return func()
            finally:
                self._inner_hookexec = old_hookexec

        return await self._async_submitter.run(wrapper)


def _formatdef(func: Callable[..., object]) -> str:
    return f"{func.__name__}{inspect.signature(func)}"
