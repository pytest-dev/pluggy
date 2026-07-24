"""
Tests for the greenlet-based async Submitter support.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from collections.abc import Awaitable
from collections.abc import Coroutine
from typing import Any
from typing import cast

import pytest

import pluggy
from pluggy._async import async_generator_to_sync
from pluggy._async import Submitter


hookspec = pluggy.HookspecMarker("test")
hookimpl = pluggy.HookimplMarker("test")


class HookSpecs:
    @hookspec
    def test_hook(self):
        pass


class AsyncPlugin:
    @hookimpl
    async def test_hook(self):
        await asyncio.sleep(0.01)
        return "async_result"


class SyncPlugin:
    @hookimpl
    def test_hook(self):
        return "sync_result"


def make_pm(*plugins: object) -> pluggy.PluginManager:
    pm = pluggy.PluginManager("test")
    pm.add_hookspecs(HookSpecs)
    for plugin in plugins:
        pm.register(plugin)
    return pm


def test_run_async_mixed_sync_and_async() -> None:
    pytest.importorskip("greenlet")
    pm = make_pm(AsyncPlugin(), SyncPlugin())

    async def run_test() -> list[str]:
        result = await pm.run_async(lambda: pm.hook.test_hook())
        return cast(list[str], result)

    result = asyncio.run(run_test())
    assert "sync_result" in result
    assert "async_result" in result


def test_run_async_with_sync_hooks_only() -> None:
    pytest.importorskip("greenlet")
    pm = make_pm(SyncPlugin())

    async def run_test() -> list[str]:
        result = await pm.run_async(lambda: pm.hook.test_hook())
        return cast(list[str], result)

    assert asyncio.run(run_test()) == ["sync_result"]


def test_awaitable_left_in_results_outside_run_async() -> None:
    """Outside run_async, awaitables are passed through (await-me-maybe)."""
    pm = make_pm(AsyncPlugin(), SyncPlugin())

    results = pm.hook.test_hook()
    assert "sync_result" in results
    awaitables = [res for res in results if isinstance(res, Awaitable)]
    assert len(awaitables) == 1

    # Awaiting the leftover coroutine still works.
    leftover = cast("Coroutine[Any, Any, str]", awaitables[0])
    assert asyncio.run(leftover) == "async_result"


def test_run_async_returning_none_succeeds() -> None:
    """Regression test: a legitimate None result must not be rejected."""
    pytest.importorskip("greenlet")
    pm = make_pm()

    async def run_test() -> None:
        return await pm.run_async(lambda: None)

    assert asyncio.run(run_test()) is None


def test_nested_run_async_rejected() -> None:
    pytest.importorskip("greenlet")
    pm = make_pm()
    inner_error: list[BaseException] = []

    def nested() -> object:
        submitter = pm._async_submitter
        # Submitter is already active - a nested run must hard-fail.
        coro = submitter.run(lambda: 1)
        try:
            coro.send(None)
        except RuntimeError as e:
            inner_error.append(e)
        finally:
            coro.close()
        return "done"

    async def run_test() -> object:
        return await pm.run_async(nested)

    assert asyncio.run(run_test()) == "done"
    assert inner_error
    assert "already active" in str(inner_error[0])


def test_run_async_propagates_sync_exception() -> None:
    pytest.importorskip("greenlet")
    pm = make_pm()

    def boom() -> None:
        raise ValueError("boom")

    async def run_test() -> None:
        await pm.run_async(boom)

    with pytest.raises(ValueError, match="boom"):
        asyncio.run(run_test())


def test_run_async_propagates_awaited_exception() -> None:
    """An exception raised while awaiting surfaces at the hook call site."""
    pytest.importorskip("greenlet")

    class FailingAsyncPlugin:
        @hookimpl
        async def test_hook(self):
            raise ValueError("async boom")

    pm = make_pm(FailingAsyncPlugin())

    async def run_test() -> None:
        await pm.run_async(lambda: pm.hook.test_hook())

    with pytest.raises(ValueError, match="async boom"):
        asyncio.run(run_test())


def test_run_async_without_greenlet() -> None:
    try:
        import greenlet  # noqa: F401

        pytest.skip("greenlet is available, cannot test the error case")
    except ImportError:  # pragma: no cover
        pm = make_pm()

        async def run_test() -> None:
            with pytest.raises(RuntimeError, match="greenlet is required"):
                await pm.run_async(lambda: "test")

        asyncio.run(run_test())


def test_require_await_outside_context() -> None:
    submitter = Submitter()

    async def coro() -> None:
        pass  # pragma: no cover

    awaitable = coro()
    with pytest.raises(RuntimeError, match="outside of async context"):
        submitter.require_await(awaitable)
    awaitable.close()


def test_maybe_submit_outside_context_returns_awaitable() -> None:
    submitter = Submitter()

    async def coro() -> str:
        return "value"

    awaitable = coro()
    assert submitter.maybe_submit(awaitable) is awaitable
    assert asyncio.run(awaitable) == "value"


def test_async_generator_to_sync_basic() -> None:
    pytest.importorskip("greenlet")

    async def simple_async_gen() -> AsyncGenerator[str]:
        yield "first"
        yield "second"

    submitter = Submitter()

    def test_func() -> tuple[list[str], Any]:
        sync_gen = async_generator_to_sync(simple_async_gen(), submitter)
        values = []
        try:
            while True:
                values.append(next(sync_gen))
        except StopIteration as e:
            return values, e.value

    values, final_value = asyncio.run(submitter.run(test_func))
    assert values == ["first", "second"]
    assert final_value is None


def test_async_generator_to_sync_with_send() -> None:
    pytest.importorskip("greenlet")

    async def async_gen_with_send() -> AsyncGenerator[str, str]:
        sent1 = yield "initial"
        sent2 = yield f"got_{sent1}"
        yield f"final_{sent2}"

    submitter = Submitter()

    def test_func() -> tuple[str, str, str, Any]:
        sync_gen = async_generator_to_sync(async_gen_with_send(), submitter)
        value1 = next(sync_gen)
        value2 = sync_gen.send("hello")
        value3 = sync_gen.send("world")
        try:
            next(sync_gen)
            raise AssertionError("should have raised StopIteration")
        except StopIteration as e:
            return value1, value2, value3, e.value

    value1, value2, value3, final = asyncio.run(submitter.run(test_func))
    assert value1 == "initial"
    assert value2 == "got_hello"
    assert value3 == "final_world"
    assert final is None


def test_async_generator_to_sync_with_exception() -> None:
    pytest.importorskip("greenlet")

    async def async_gen_with_exception() -> AsyncGenerator[str]:
        try:
            yield "before_exception"
            yield "should_not_reach"
        except ValueError as e:
            yield f"caught_{e}"

    submitter = Submitter()

    def test_func() -> tuple[str, str, Any]:
        sync_gen = async_generator_to_sync(async_gen_with_exception(), submitter)
        value1 = next(sync_gen)
        value2 = sync_gen.throw(ValueError("test_error"))
        try:
            next(sync_gen)
            raise AssertionError("should have raised StopIteration")
        except StopIteration as e:
            return value1, value2, e.value

    value1, value2, final = asyncio.run(submitter.run(test_func))
    assert value1 == "before_exception"
    assert value2 == "caught_test_error"
    assert final is None


def test_async_generator_to_sync_inactive_submitter() -> None:
    async def simple_async_gen() -> AsyncGenerator[str]:
        yield "test"  # pragma: no cover

    submitter = Submitter()

    with pytest.raises(RuntimeError, match="outside of async context"):
        sync_gen = async_generator_to_sync(simple_async_gen(), submitter)
        next(sync_gen)


def test_submitter_repr() -> None:
    submitter = Submitter()
    assert repr(submitter) == "<Submitter active=False>"
