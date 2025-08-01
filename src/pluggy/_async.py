"""
Async support for pluggy using greenlets.

This module provides async functionality for pluggy, allowing hook implementations
to return awaitable objects that are automatically awaited when running in an
async context.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Generator
from typing import Any
from typing import TYPE_CHECKING
from typing import TypeVar


_T = TypeVar("_T")
_Y = TypeVar("_Y")
_S = TypeVar("_S")
_R = TypeVar("_R")

if TYPE_CHECKING:
    import greenlet


def make_greenlet(func: Callable[..., Any]) -> greenlet.greenlet:
    """indirection to defer import"""
    import greenlet

    return greenlet.greenlet(func)


class Submitter:
    # practice we expect te root greenlet to be the key submitter
    _active_submitter: greenlet.greenlet | None

    def __init__(self) -> None:
        self._active_submitter = None

    def __repr__(self) -> str:
        return f"<Submitter active={self._active_submitter is not None}>"

    def maybe_submit(self, coro: Awaitable[_T]) -> _T | Awaitable[_T]:
        """await an awaitable if active, else return it

        this enables backward compatibility for datasette
        and https://simonwillison.net/2020/Sep/2/await-me-maybe/
        """
        active = self._active_submitter
        if active is not None:
            # We're in a greenlet context, switch with the awaitable
            # The parent will await it and switch back with the result
            res: _T = active.switch(coro)
            return res
        else:
            return coro

    def require_await(self, coro: Awaitable[_T]) -> _T:
        """await an awaitable, raising an error if not in async context

        this is for cases where async context is required
        """
        active = self._active_submitter
        if active is not None:
            # Switch to the active submitter greenlet with the awaitable
            # The active submitter will await it and switch back with the result
            res: _T = active.switch(coro)
            return res
        else:
            raise RuntimeError("require_await called outside of async context")

    async def run(self, sync_func: Callable[[], _T]) -> _T:
        """Run a synchronous function with async support."""
        try:
            import greenlet
        except ImportError:
            raise RuntimeError("greenlet is required for async support")

        if self._active_submitter is not None:
            raise RuntimeError("Submitter is already active")

        # Set the current greenlet as the main async context
        main_greenlet = greenlet.getcurrent()
        result: _T | None = None
        exception: BaseException | None = None

        def greenlet_func() -> None:
            nonlocal result, exception
            try:
                result = sync_func()
            except BaseException as e:
                exception = e

        # Create the worker greenlet
        worker_greenlet = greenlet.greenlet(greenlet_func)
        # Set the active submitter to the main greenlet so maybe_submit can switch back
        self._active_submitter = main_greenlet

        try:
            # Switch to the worker greenlet and handle any awaitables it passes back
            awaitable = worker_greenlet.switch()
            while awaitable is not None:
                # Await the awaitable and send the result back to the greenlet
                awaited_result = await awaitable
                awaitable = worker_greenlet.switch(awaited_result)
        except Exception as e:
            # If something goes wrong, try to send the exception to the greenlet
            try:
                worker_greenlet.throw(e)
            except BaseException as inner_e:
                exception = inner_e
        finally:
            self._active_submitter = None

        if exception is not None:
            raise exception
        if result is None:
            raise RuntimeError("Function completed without setting result")
        return result


def async_generator_to_sync(
    async_gen: AsyncGenerator[_Y, _S], submitter: Submitter
) -> Generator[_Y, _S, None]:
    """Convert an async generator to a sync generator using a Submitter.

    This helper allows wrapper implementations to use async generators while
    maintaining compatibility with the sync generator interface expected by
    the hook system.

    Args:
        async_gen: The async generator to convert
        submitter: The Submitter to use for awaiting async operations

    Yields:
        Values from the async generator

    Returns:
        None (async generators don't return values)

    Example:
        async def my_async_wrapper():
            yield  # Setup phase
            result = await some_async_operation()

        # In a wrapper hook implementation:
        def my_wrapper_hook():
            async_gen = my_async_wrapper()
            gen = async_generator_to_sync(async_gen, submitter)
            try:
                while True:
                    value = next(gen)
                    yield value
            except StopIteration:
                return
    """
    try:
        # Start the async generator
        value = submitter.require_await(async_gen.__anext__())

        while True:
            try:
                # Yield the value and get the sent value
                sent_value = yield value

                # Send the value to the async generator and get the next value
                try:
                    value = submitter.require_await(async_gen.asend(sent_value))
                except StopAsyncIteration:
                    # Async generator completed
                    return

            except GeneratorExit:
                # Generator is being closed, close the async generator
                try:
                    submitter.require_await(async_gen.aclose())
                except StopAsyncIteration:
                    pass
                raise

            except BaseException as exc:
                # Exception was thrown into the generator,
                #  throw it into the async generator
                try:
                    value = submitter.require_await(async_gen.athrow(exc))
                except StopAsyncIteration:
                    # Async generator completed
                    return
                except StopIteration as sync_stop_exc:
                    # Re-raise StopIteration as it was passed through
                    raise sync_stop_exc

    except StopAsyncIteration:
        # Async generator completed normally
        return
