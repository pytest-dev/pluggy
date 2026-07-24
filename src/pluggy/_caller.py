"""
Hook callers and relay.
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import MutableSequence
from collections.abc import Sequence
from collections.abc import Set
from typing import Any
from typing import cast
from typing import Final
from typing import final
from typing import Protocol
from typing import runtime_checkable
from typing import TYPE_CHECKING
from typing import TypeAlias
from typing import TypeVar

from ._config import HookimplConfiguration
from ._config import hookspec_config_from_mapping
from ._config import HookspecConfiguration
from ._decorators import _Namespace
from ._decorators import HookSpec
from ._implementation import _Plugin
from ._implementation import HookImpl
from ._implementation import NormalImpl
from ._implementation import WrapperImpl


_HookExec: TypeAlias = Callable[
    [str, Sequence[NormalImpl], Sequence[WrapperImpl], Mapping[str, object], bool],
    "object | list[object]",
]

_T_HookImpl = TypeVar("_T_HookImpl", bound=HookImpl)


def _insert_hookimpl_into_list(
    hookimpl: _T_HookImpl, target_list: MutableSequence[_T_HookImpl]
) -> None:
    """Insert a hookimpl into the target list maintaining proper ordering.

    The ordering is: [trylast, normal, tryfirst].
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


def _coerce_spec_config(
    spec_config: HookspecConfiguration | Mapping[str, Any],
) -> HookspecConfiguration:
    """Accept a configuration object or a legacy mapping (pytest shim)."""
    if isinstance(spec_config, HookspecConfiguration):
        return spec_config
    return hookspec_config_from_mapping(spec_config)


@runtime_checkable
class HookCaller(Protocol):
    """Protocol defining the interface for hook callers.

    .. versionchanged:: 1.7
        ``HookCaller`` is now a :class:`~typing.Protocol` (runtime checkable).
        The concrete implementations are :class:`NormalHookCaller`,
        :class:`HistoricHookCaller` and ``SubsetHookCaller``.
    """

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
        """Whether this caller is :ref:`historic <historic>`."""
        ...

    def get_hookimpls(self) -> list[HookImpl]:
        """Get all registered hook implementations for this hook."""
        ...

    def set_specification(
        self,
        specmodule_or_class: _Namespace,
        spec_config: HookspecConfiguration | Mapping[str, Any],
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


@final
class HookRelay:
    """Hook holder object for performing 1:N hook calls where N is the number
    of registered plugins."""

    __slots__ = ("__dict__",)

    def __init__(self) -> None:
        """:meta private:"""

    if TYPE_CHECKING:

        def __getattr__(self, name: str) -> NormalHookCaller | HistoricHookCaller: ...


# Historical name (pluggy<=1.2), kept for backward compatibility.
_HookRelay = HookRelay


_CallHistory: TypeAlias = list[
    tuple[Mapping[str, object], Callable[[Any], None] | None]
]


class NormalHookCaller:
    """A caller of all registered implementations of a hook specification."""

    __slots__ = (
        "name",
        "spec",
        "_hookexec",
        "_normal_hookimpls",
        "_wrapper_hookimpls",
    )

    def __init__(
        self,
        name: str,
        hook_execute: _HookExec,
        specmodule_or_class: _Namespace | None = None,
        spec_config: HookspecConfiguration | None = None,
    ) -> None:
        """:meta private:"""
        #: Name of the hook getting called.
        self.name: Final = name
        self._hookexec: Final = hook_execute
        # Split hook implementations into two lists for simpler management:
        # Normal hooks: [trylast, normal, tryfirst]
        # Wrapper hooks: [trylast, normal, tryfirst]
        self._normal_hookimpls: Final[list[NormalImpl]] = []
        self._wrapper_hookimpls: Final[list[WrapperImpl]] = []
        # TODO: Document, or make private.
        self.spec: HookSpec | None = None
        if specmodule_or_class is not None:
            assert spec_config is not None
            self.set_specification(specmodule_or_class, spec_config)

    # TODO: Document, or make private.
    def has_spec(self) -> bool:
        return self.spec is not None

    # TODO: Document, or make private.
    def set_specification(
        self,
        specmodule_or_class: _Namespace,
        spec_config: HookspecConfiguration | Mapping[str, Any],
    ) -> None:
        if self.spec is not None:
            raise ValueError(
                f"Hook {self.spec.name!r} is already registered "
                f"within namespace {self.spec.namespace}"
            )
        config = _coerce_spec_config(spec_config)
        if config.historic:
            raise ValueError(
                f"NormalHookCaller cannot handle historic hooks. "
                f"Use HistoricHookCaller for {self.name!r}"
            )
        self.spec = HookSpec(specmodule_or_class, self.name, config)

    def is_historic(self) -> bool:
        """Whether this caller is :ref:`historic <historic>`."""
        return False

    def _remove_plugin(self, plugin: _Plugin) -> None:
        """Remove all hook implementations registered by the given plugin."""
        remaining_normal = [i for i in self._normal_hookimpls if i.plugin != plugin]
        remaining_wrapper = [i for i in self._wrapper_hookimpls if i.plugin != plugin]
        if len(remaining_normal) == len(self._normal_hookimpls) and len(
            remaining_wrapper
        ) == len(self._wrapper_hookimpls):
            raise ValueError(f"plugin {plugin!r} not found")
        self._normal_hookimpls[:] = remaining_normal
        self._wrapper_hookimpls[:] = remaining_wrapper

    def get_hookimpls(self) -> list[HookImpl]:
        """Get all registered hook implementations for this hook.

        Normal implementations come first, then wrappers (matching the
        historical combined-list ordering).
        """
        return [*self._normal_hookimpls, *self._wrapper_hookimpls]

    def _add_hookimpl(self, hookimpl: HookImpl) -> None:
        """Add an implementation to the callback chain."""
        if isinstance(hookimpl, WrapperImpl):
            _insert_hookimpl_into_list(hookimpl, self._wrapper_hookimpls)
        else:
            assert isinstance(hookimpl, NormalImpl), (
                "normal hook implementations must be NormalImpl instances"
            )
            _insert_hookimpl_into_list(hookimpl, self._normal_hookimpls)

    def __repr__(self) -> str:
        return f"<NormalHookCaller {self.name!r}>"

    def _verify_all_args_are_provided(self, kwargs: Mapping[str, object]) -> None:
        if self.spec:
            self.spec.verify_all_args_are_provided(kwargs)

    def __call__(self, **kwargs: object) -> Any:
        """Call the hook.

        Only accepts keyword arguments, which should match the hook
        specification.

        Returns the result(s) of calling all registered plugins, see
        :ref:`calling`.
        """
        self._verify_all_args_are_provided(kwargs)
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
        """Historic calls are only supported by historic hooks."""
        raise AssertionError(
            f"Hook {self.name!r} is not historic - cannot call call_historic"
        )

    def call_extra(
        self, methods: Sequence[Callable[..., object]], kwargs: Mapping[str, object]
    ) -> Any:
        """Call the hook with some additional temporarily participating
        methods using the specified ``kwargs`` as call parameters, see
        :ref:`call_extra`."""
        self._verify_all_args_are_provided(kwargs)
        config = HookimplConfiguration()
        normal_hookimpls = self._normal_hookimpls.copy()
        for method in methods:
            hookimpl = config.create_hookimpl(None, "<temp>", method)
            # call_extra only supports normal implementations.
            assert isinstance(hookimpl, NormalImpl)
            _insert_hookimpl_into_list(hookimpl, normal_hookimpls)
        firstresult = self.spec.config.firstresult if self.spec else False
        return self._hookexec(
            self.name,
            normal_hookimpls,
            self._wrapper_hookimpls.copy(),
            kwargs,
            firstresult,
        )

    def _maybe_apply_history(self, method: HookImpl) -> None:
        """Nothing to do - normal hooks have no call history."""


# Historical name (pluggy<=1.2), kept for backward compatibility.
_HookCaller = NormalHookCaller


class HistoricHookCaller:
    """A caller for historic hook specifications that memorizes and replays
    calls.

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

    spec: HookSpec

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
        self.name: Final = name
        self._hookexec: Final = hook_execute
        # The hookimpls list for historic hooks (no wrappers supported).
        self._hookimpls: Final[list[NormalImpl]] = []
        self._call_history: Final[_CallHistory] = []
        # TODO: Document, or make private.
        self.spec = HookSpec(specmodule_or_class, name, spec_config)

    def has_spec(self) -> bool:
        return True

    def set_specification(
        self,
        specmodule_or_class: _Namespace,
        spec_config: HookspecConfiguration | Mapping[str, Any],
    ) -> None:
        """Historic hooks cannot have their specification changed."""
        raise ValueError(
            f"Hook {self.spec.name!r} is already registered "
            f"within namespace {self.spec.namespace}"
        )

    def is_historic(self) -> bool:
        """Whether this caller is :ref:`historic <historic>`."""
        return True

    def _remove_plugin(self, plugin: _Plugin) -> None:
        remaining = [impl for impl in self._hookimpls if impl.plugin != plugin]
        if len(remaining) == len(self._hookimpls):
            raise ValueError(f"plugin {plugin!r} not found")
        self._hookimpls[:] = remaining

    def get_hookimpls(self) -> list[HookImpl]:
        """Get all registered hook implementations for this hook."""
        return list(self._hookimpls)

    def _add_hookimpl(self, hookimpl: HookImpl) -> None:
        """Add an implementation to the callback chain."""
        assert isinstance(hookimpl, NormalImpl), (
            "historic hooks do not support wrappers"
        )
        _insert_hookimpl_into_list(hookimpl, self._hookimpls)

    def __repr__(self) -> str:
        return f"<HistoricHookCaller {self.name!r}>"

    def __call__(self, **kwargs: object) -> Any:
        """Historic hooks cannot be called directly.

        Use :meth:`call_historic` instead.
        """
        raise AssertionError(
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
        """Historic hooks do not support call_extra."""
        raise AssertionError(
            "Cannot directly call a historic hook - use call_historic instead."
        )

    def _maybe_apply_history(self, method: HookImpl) -> None:
        """Apply call history to a new hookimpl."""
        assert isinstance(method, NormalImpl)
        for kwargs, result_callback in self._call_history:
            res = self._hookexec(self.name, [method], [], kwargs, False)
            if res and result_callback is not None:
                # XXX: remember firstresult isn't compat with historic
                assert isinstance(res, list)
                result_callback(res[0])


class SubsetHookCaller:
    """A proxy to another hook caller which manages calls to all registered
    plugins except the ones from remove_plugins."""

    # `subset_hook_caller` used to be implemented by creating a full-fledged
    # HookCaller, copying all hookimpls from the original. This had problems
    # with memory leaks (#346) and historic calls (#347), which make a proxy
    # approach better.

    __slots__ = (
        "_orig",
        "_remove_plugins",
    )

    def __init__(
        self,
        orig: NormalHookCaller | HistoricHookCaller,
        remove_plugins: Set[_Plugin],
    ) -> None:
        """:meta private:"""
        self._orig: Final = orig
        self._remove_plugins: Final = remove_plugins

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

    def _get_filtered(self, hookimpls: Sequence[_T_HookImpl]) -> list[_T_HookImpl]:
        """Filter out hook implementations from removed plugins."""
        return [impl for impl in hookimpls if impl.plugin not in self._remove_plugins]

    def get_hookimpls(self) -> list[HookImpl]:
        """Get filtered hook implementations for this hook."""
        return self._get_filtered(self._orig.get_hookimpls())

    def set_specification(
        self,
        specmodule_or_class: _Namespace,
        spec_config: HookspecConfiguration | Mapping[str, Any],
    ) -> None:
        """SubsetHookCaller is a read-only proxy - specs cannot be set."""
        raise RuntimeError(
            f"Cannot set specification on SubsetHookCaller {self.name!r} - "
            "it is a read-only proxy to another hook caller"
        )

    def __call__(self, **kwargs: object) -> Any:
        """Call the hook with filtered implementations."""
        if self.is_historic():
            raise AssertionError(
                "Cannot directly call a historic hook - use call_historic instead."
            )
        orig = self._orig
        assert isinstance(orig, NormalHookCaller)
        if orig.spec:
            orig.spec.verify_all_args_are_provided(kwargs)
        firstresult = orig.spec.config.firstresult if orig.spec else False
        return orig._hookexec(
            self.name,
            self._get_filtered(orig._normal_hookimpls),
            self._get_filtered(orig._wrapper_hookimpls),
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
        """
        orig = self._orig
        assert isinstance(orig, HistoricHookCaller), (
            f"Hook {self.name!r} is not historic - cannot call call_historic"
        )
        kwargs = kwargs or {}
        orig.spec.verify_all_args_are_provided(kwargs)
        # History is shared with the original caller.
        orig._call_history.append((kwargs, result_callback))
        res = orig._hookexec(
            self.name, self._get_filtered(orig._hookimpls), [], kwargs, False
        )
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
        orig = self._orig
        if self.is_historic():
            raise AssertionError(
                "Cannot directly call a historic hook - use call_historic instead."
            )
        assert isinstance(orig, NormalHookCaller)
        if orig.spec:
            orig.spec.verify_all_args_are_provided(kwargs)
        config = HookimplConfiguration()
        normal_impls = self._get_filtered(orig._normal_hookimpls)
        for method in methods:
            hookimpl = config.create_hookimpl(None, "<temp>", method)
            assert isinstance(hookimpl, NormalImpl)
            _insert_hookimpl_into_list(hookimpl, normal_impls)
        firstresult = orig.spec.config.firstresult if orig.spec else False
        return orig._hookexec(
            self.name,
            normal_impls,
            self._get_filtered(orig._wrapper_hookimpls),
            kwargs,
            firstresult,
        )

    def __repr__(self) -> str:
        return f"<SubsetHookCaller {self.name!r}>"


# Historical name, kept for backward compatibility.
_SubsetHookCaller = SubsetHookCaller


if TYPE_CHECKING:
    # Verify the concrete callers satisfy the HookCaller protocol.
    _: list[HookCaller] = [
        cast(NormalHookCaller, None),
        cast(HistoricHookCaller, None),
        cast(SubsetHookCaller, None),
    ]
