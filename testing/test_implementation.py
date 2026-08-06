"""
Tests for the HookImpl hierarchy and the CompletionHook setup API.
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Generator
from typing import Any

import pytest

from pluggy import HookCallError
from pluggy import HookImpl
from pluggy import HookimplConfiguration
from pluggy import HookimplMarker
from pluggy import HookspecMarker
from pluggy import NormalImpl
from pluggy import PluginManager
from pluggy import WrapperImpl
from pluggy._implementation import CompletionHook


hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


def func(arg: object) -> object:
    return arg


def wrapper_func(arg: object) -> Generator[None, object, object]:
    return (yield)


class TestCreateHookimpl:
    def test_normal_config_returns_normal_impl(self) -> None:
        config = HookimplConfiguration()
        impl = config.create_hookimpl(None, "test", func)
        assert type(impl) is NormalImpl
        assert isinstance(impl, HookImpl)
        assert impl.hookimpl_config is config

    def test_wrapper_config_returns_wrapper_impl(self) -> None:
        config = HookimplConfiguration(wrapper=True)
        impl = config.create_hookimpl(None, "test", wrapper_func)
        assert type(impl) is WrapperImpl

    def test_hookwrapper_config_returns_wrapper_impl(self) -> None:
        config = HookimplConfiguration(hookwrapper=True)
        impl = config.create_hookimpl(None, "test", wrapper_func)
        assert type(impl) is WrapperImpl

    def test_normal_impl_rejects_wrapper_config(self) -> None:
        config = HookimplConfiguration(wrapper=True)
        with pytest.raises(ValueError, match="Use WrapperImpl"):
            NormalImpl(None, "test", wrapper_func, config)

    def test_wrapper_impl_rejects_normal_config(self) -> None:
        config = HookimplConfiguration()
        with pytest.raises(ValueError, match="Use NormalImpl"):
            WrapperImpl(None, "test", func, config)

    def test_opts_alias(self) -> None:
        config = HookimplConfiguration(tryfirst=True)
        impl = config.create_hookimpl(None, "test", func)
        assert impl.opts is config


class TestGetCallArgs:
    def test_binds_in_argname_order(self) -> None:
        def f(b: object, a: object) -> None:
            pass

        impl = HookimplConfiguration().create_hookimpl(None, "test", f)
        assert impl._get_call_args({"a": 1, "b": 2, "extra": 3}) == [2, 1]

    def test_missing_argument_raises_hook_call_error(self) -> None:
        impl = HookimplConfiguration().create_hookimpl(None, "test", func)
        with pytest.raises(HookCallError, match="must provide argument 'arg'"):
            impl._get_call_args({})


def make_wrapper_impl(
    function: Callable[..., Any], *, hookwrapper: bool = False
) -> WrapperImpl:
    config = HookimplConfiguration(wrapper=not hookwrapper, hookwrapper=hookwrapper)
    impl = config.create_hookimpl(None, "test", function)
    assert isinstance(impl, WrapperImpl)
    return impl


class TestSetupAndGetCompletionHook:
    def test_returns_completion_hook_protocol_instance(self) -> None:
        impl = make_wrapper_impl(wrapper_func)
        completion = impl.setup_and_get_completion_hook("myhook", {"arg": 1})
        assert isinstance(completion, CompletionHook)
        assert completion(21, None) == (21, None)

    def test_setup_runs_code_before_yield(self) -> None:
        events: list[str] = []

        def wrapper() -> Generator[None, object, object]:
            events.append("setup")
            res = yield
            events.append("teardown")
            return res

        impl = make_wrapper_impl(wrapper)
        completion = impl.setup_and_get_completion_hook("myhook", {})
        assert events == ["setup"]
        assert completion("x", None) == ("x", None)
        assert events == ["setup", "teardown"]

    def test_completion_replaces_result(self) -> None:
        def wrapper() -> Generator[None, object, object]:
            res = yield
            assert isinstance(res, int)
            return res + 1

        impl = make_wrapper_impl(wrapper)
        completion = impl.setup_and_get_completion_hook("myhook", {})
        assert completion(41, None) == (42, None)

    def test_completion_can_swallow_exception(self) -> None:
        def wrapper() -> Generator[None, object, object]:
            try:
                yield
            except ValueError:
                return "fallback"
            raise AssertionError("unreachable")

        impl = make_wrapper_impl(wrapper)
        completion = impl.setup_and_get_completion_hook("myhook", {})
        result, exception = completion(None, ValueError("boom"))
        assert result == "fallback"
        assert exception is None

    def test_completion_passes_through_unhandled_exception(self) -> None:
        impl = make_wrapper_impl(wrapper_func)
        completion = impl.setup_and_get_completion_hook("myhook", {"arg": 1})
        exc = ValueError("boom")
        result, exception = completion("kept", exc)
        assert result == "kept"
        assert exception is exc

    def test_completion_can_raise_new_exception(self) -> None:
        def wrapper() -> Generator[None, object, object]:
            yield
            raise RuntimeError("replaced")

        impl = make_wrapper_impl(wrapper)
        completion = impl.setup_and_get_completion_hook("myhook", {})
        result, exception = completion("x", None)
        assert result == "x"
        assert isinstance(exception, RuntimeError)
        assert str(exception) == "replaced"

    def test_did_not_yield_raises(self) -> None:
        def no_yield() -> Generator[None, object, object]:
            return "nope"
            yield  # type: ignore[unreachable] # pragma: no cover

        impl = make_wrapper_impl(no_yield)
        with pytest.raises(RuntimeError, match="did not yield"):
            impl.setup_and_get_completion_hook("myhook", {})

    def test_second_yield_raises(self) -> None:
        def two_yields() -> Generator[None, object, None]:
            yield
            yield

        impl = make_wrapper_impl(two_yields)
        completion = impl.setup_and_get_completion_hook("myhook", {})
        result, exception = completion("x", None)
        assert result == "x"
        assert isinstance(exception, RuntimeError)
        assert "has second yield" in str(exception)

    def test_old_style_hookwrapper_receives_result_object(self) -> None:
        seen: list[object] = []

        def old_style(arg: object) -> Generator[None, object, None]:
            outcome = yield
            seen.append(outcome)
            outcome.force_result(f"forced: {arg}")  # type: ignore[attr-defined]

        impl = make_wrapper_impl(old_style, hookwrapper=True)
        completion = impl.setup_and_get_completion_hook("myhook", {"arg": "a"})
        result, exception = completion("orig", None)
        assert result == "forced: a"
        assert exception is None
        assert seen and seen[0].__class__.__name__ == "Result"


class TestRegistrationCreatesSubclasses:
    def test_registered_impl_types(self) -> None:
        class Spec:
            @hookspec
            def myhook(self, arg: object) -> None:
                pass

        class Plugin:
            @hookimpl
            def myhook(self, arg: object) -> object:
                return arg

            @hookimpl(wrapper=True)
            def myhook_wrapper(self, arg: object) -> Generator[None, object, object]:
                return (yield)

        pm = PluginManager("example")
        pm.add_hookspecs(Spec)
        pm.register(Plugin())
        impls = {type(impl).__name__ for impl in pm.hook.myhook.get_hookimpls()}
        assert impls == {"NormalImpl"}
        wrapper_impls = pm.hook.myhook_wrapper.get_hookimpls()
        assert {type(impl).__name__ for impl in wrapper_impls} == {"WrapperImpl"}
