import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from typing import cast

import pytest

import pluggy
from pluggy._async import async_generator_to_sync
from pluggy._async import Submitter


pytest_plugins = ["pytester"]

hookimpl = pluggy.HookimplMarker("test")
hookspec = pluggy.HookspecMarker("test")


class AsyncPlugin:
    @hookimpl
    async def test_hook(self):
        await asyncio.sleep(0.01)  # Small delay to make it actually async
        return "async_result"


class SyncPlugin:
    @hookimpl
    def test_hook(self):
        return "sync_result"


def test_run_async_with_greenlet_available():
    """Test that run_async works when greenlet is available."""
    pytest.importorskip("greenlet")

    pm = pluggy.PluginManager("test")

    class HookSpec:
        @hookspec
        def test_hook(self):
            pass

    pm.add_hookspecs(HookSpec)
    pm.register(AsyncPlugin())
    pm.register(SyncPlugin())

    async def run_test() -> list[str]:
        result = await pm.run_async(lambda: pm.hook.test_hook())
        return cast(list[str], result)

    # Run the async function
    result: list[str] = asyncio.run(run_test())

    # Should have both sync and async results
    assert "sync_result" in result
    assert "async_result" in result


def test_run_async_without_greenlet():
    """Test that run_async raises appropriate error when greenlet is not available."""
    # We can't easily mock the greenlet import since it's already loaded,
    # so we'll skip this test if greenlet is available
    try:
        import greenlet  # noqa: F401

        pytest.skip("greenlet is available, cannot test the error case")
    except ImportError:
        pm = pluggy.PluginManager("test")

        async def run_test() -> None:
            with pytest.raises(RuntimeError, match="greenlet is required"):
                await pm.run_async(lambda: "test")

        asyncio.run(run_test())


def test_run_async_with_sync_hooks_only():
    """Test that run_async works even with only sync hooks."""
    pytest.importorskip("greenlet")

    pm = pluggy.PluginManager("test")

    class HookSpec:
        @hookspec
        def test_hook(self):
            pass

    pm.add_hookspecs(HookSpec)
    pm.register(SyncPlugin())

    async def run_test() -> list[str]:
        result = await pm.run_async(lambda: pm.hook.test_hook())
        return cast(list[str], result)

    result: list[str] = asyncio.run(run_test())
    assert result == ["sync_result"]


def test_async_generator_to_sync_basic():
    """Test basic async generator to sync generator conversion."""
    pytest.importorskip("greenlet")

    async def simple_async_gen() -> AsyncGenerator[str, None]:
        yield "first"
        yield "second"

    submitter = Submitter()

    def test_func() -> tuple[list[str], Any]:
        async_gen = simple_async_gen()
        sync_gen = async_generator_to_sync(async_gen, submitter)

        values = []
        try:
            while True:
                value = next(sync_gen)
                values.append(value)
        except StopIteration as e:
            return values, e.value

    values, final_value = asyncio.run(submitter.run(test_func))
    assert values == ["first", "second"]
    assert final_value is None


def test_async_generator_to_sync_with_send():
    """Test async generator to sync generator with send values."""
    pytest.importorskip("greenlet")

    async def async_gen_with_send() -> AsyncGenerator[str, str]:
        sent1 = yield "initial"
        sent2 = yield f"got_{sent1}"
        yield f"final_{sent2}"

    submitter = Submitter()

    def test_func() -> tuple[str, str, str, Any]:
        async_gen = async_gen_with_send()
        sync_gen = async_generator_to_sync(async_gen, submitter)

        # Get first value
        value1 = next(sync_gen)
        # Send a value
        value2 = sync_gen.send("hello")
        # Send another value and get final result
        value3 = sync_gen.send("world")
        try:
            next(sync_gen)
            assert False, "Should have raised StopIteration"
        except StopIteration as e:
            return value1, value2, value3, e.value

    value1, value2, value3, final = asyncio.run(submitter.run(test_func))
    assert value1 == "initial"
    assert value2 == "got_hello"
    assert value3 == "final_world"
    assert final is None


def test_async_generator_to_sync_with_exception():
    """Test async generator to sync generator with exception handling."""
    pytest.importorskip("greenlet")

    async def async_gen_with_exception() -> AsyncGenerator[str, None]:
        try:
            yield "before_exception"
            yield "should_not_reach"
        except ValueError as e:
            yield f"caught_{e}"

    submitter = Submitter()

    def test_func() -> tuple[str, str, Any]:
        async_gen = async_gen_with_exception()
        sync_gen = async_generator_to_sync(async_gen, submitter)

        # Get first value
        value1 = next(sync_gen)

        # Throw exception into generator
        value2 = sync_gen.throw(ValueError("test_error"))
        # Get final result
        try:
            next(sync_gen)
            assert False, "Should have raised StopIteration"
        except StopIteration as e:
            return value1, value2, e.value

    res = asyncio.run(submitter.run(test_func))

    value1, value2, final = res
    assert value1 == "before_exception"
    assert value2 == "caught_test_error"
    assert final is None


def test_async_generator_to_sync_inactive_submitter():
    """Test that async_generator_to_sync raises error with inactive submitter."""
    pytest.importorskip("greenlet")

    async def simple_async_gen() -> AsyncGenerator[str, None]:
        yield "test"

    submitter = Submitter()
    # Don't activate the submitter

    with pytest.raises(
        RuntimeError, match="require_await called outside of async context"
    ):
        async_gen = simple_async_gen()
        sync_gen = async_generator_to_sync(async_gen, submitter)
        next(sync_gen)
