"""
Async support for pluggy using greenlets.

This module provides async functionality for pluggy, allowing hook
implementations to return awaitable objects that are automatically awaited
when running in an async context (see :meth:`PluginManager.run_async
<pluggy.PluginManager.run_async>`).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Generator
from typing import Any
from typing import cast
from typing import Final
from typing import TYPE_CHECKING
from typing import TypeVar


_T = TypeVar("_T")
_Y = TypeVar("_Y")
_S = TypeVar("_S")

if TYPE_CHECKING:
    import greenlet


#: Sentinel distinguishing "worker never completed" from a legitimate
#: ``None`` result.
_UNSET: Final = object()


class Submitter:
    """Bridge between synchronous hook execution and an async event loop.

    While :meth:`run` is active, awaitables passed to :meth:`maybe_submit` or
    :meth:`require_await` are switched to the awaiting parent greenlet, which
    awaits them and switches the result back. When inactive,
    :meth:`maybe_submit` passes awaitables through unchanged
    ("await-me-maybe").
    """

    _active_submitter: greenlet.greenlet | None

    def __init__(self) -> None:
        self._active_submitter = None

    def __repr__(self) -> str:
        return f"<Submitter active={self._active_submitter is not None}>"

    def maybe_submit(self, coro: Awaitable[_T]) -> _T | Awaitable[_T]:
        """Await an awaitable if active, else return it unchanged.

        This enables backward compatibility for datasette
        and https://simonwillison.net/2020/Sep/2/await-me-maybe/
        """
        active = self._active_submitter
        if active is not None:
            # We're in a greenlet context; switch to the parent with the
            # awaitable. The parent awaits it and switches back the result.
            res: _T = active.switch(coro)
            return res
        else:
            return coro

    def require_await(self, coro: Awaitable[_T]) -> _T:
        """Await an awaitable, raising an error if not in async context."""
        active = self._active_submitter
        if active is not None:
            res: _T = active.switch(coro)
            return res
        else:
            raise RuntimeError("require_await called outside of async context")

    async def run(self, sync_func: Callable[[], _T]) -> _T:
        """Run a synchronous function in a worker greenlet with async support.

        Awaitables submitted by hook implementations during the call are
        awaited on this coroutine's event loop.
        """
        try:
            import greenlet
        except ImportError:
            raise RuntimeError("greenlet is required for async support") from None

        if self._active_submitter is not None:
            raise RuntimeError("Submitter is already active")

        main_greenlet = greenlet.getcurrent()
        result: object = _UNSET
        exception: BaseException | None = None

        def greenlet_func() -> None:
            nonlocal result, exception
            try:
                result = sync_func()
            except BaseException as e:
                exception = e

        worker_greenlet = greenlet.greenlet(greenlet_func)
        # Let maybe_submit/require_await switch back to this greenlet.
        self._active_submitter = main_greenlet
        try:
            # Run the worker; every switch back carries an awaitable to
            # process, until the worker finishes (switching back None).
            awaitable = worker_greenlet.switch()
            while awaitable is not None:
                try:
                    awaited_result = await awaitable
                except BaseException as e:
                    # Raise at the submission site inside the worker.
                    awaitable = worker_greenlet.throw(e)
                else:
                    awaitable = worker_greenlet.switch(awaited_result)
        finally:
            self._active_submitter = None

        if exception is not None:
            raise exception
        assert result is not _UNSET, "worker greenlet did not complete"
        return cast(_T, result)


def async_generator_to_sync(
    async_gen: AsyncGenerator[_Y, _S], submitter: Submitter
) -> Generator[_Y, _S, None]:
    """Convert an async generator to a sync generator using a `Submitter`.

    This helper allows wrapper implementations to use async generators while
    maintaining compatibility with the sync generator interface expected by
    the hook system. The submitter must be active (i.e. the generator must be
    consumed under :meth:`Submitter.run`).
    """
    try:
        # Start the async generator.
        value = submitter.require_await(async_gen.__anext__())

        while True:
            try:
                sent_value = yield value
                try:
                    value = submitter.require_await(async_gen.asend(sent_value))
                except StopAsyncIteration:
                    return

            except GeneratorExit:
                # Generator is being closed; close the async generator too.
                submitter.require_await(cast(Awaitable[Any], async_gen.aclose()))
                raise

            except BaseException as exc:
                # Exception was thrown into the generator; forward it into
                # the async generator.
                try:
                    value = submitter.require_await(async_gen.athrow(exc))
                except StopAsyncIteration:
                    return

    except StopAsyncIteration:
        return
