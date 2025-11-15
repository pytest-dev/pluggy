"""
Call loop machinery
"""

from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Generator
from collections.abc import Mapping
from collections.abc import Sequence
from typing import cast
from typing import NoReturn
from typing import TYPE_CHECKING
import warnings


if TYPE_CHECKING:
    from ._async import Submitter
from ._hook_callers import HookImpl
from ._hook_callers import WrapperImpl
from ._result import Result
from ._warnings import PluggyTeardownRaisedWarning


# Need to distinguish between old- and new-style hook wrappers.
# Wrapping with a tuple is the fastest type-safe way I found to do it.
Teardown = Generator[None, object, object]


def run_old_style_hookwrapper(
    hook_impl: WrapperImpl, hook_name: str, args: Sequence[object]
) -> Teardown:
    """
    backward compatibility wrapper to run a old style hookwrapper as a wrapper
    """

    teardown: Teardown = cast(Teardown, hook_impl.function(*args))
    try:
        next(teardown)
    except StopIteration:
        _raise_wrapfail(teardown, "did not yield")
    try:
        res = yield
        result = Result(res, None)
    except BaseException as exc:
        result = Result(None, exc)
    try:
        teardown.send(result)
    except StopIteration:
        pass
    except BaseException as e:
        _warn_teardown_exception(hook_name, hook_impl, e)
        raise
    else:
        _raise_wrapfail(teardown, "has second yield")
    finally:
        teardown.close()
    return result.get_result()


def _raise_wrapfail(
    wrap_controller: Generator[None, object, object],
    msg: str,
) -> NoReturn:
    co = wrap_controller.gi_code  # type: ignore[attr-defined]
    raise RuntimeError(
        f"wrap_controller at {co.co_name!r} {co.co_filename}:{co.co_firstlineno} {msg}"
    )


def _warn_teardown_exception(
    hook_name: str, hook_impl: WrapperImpl, e: BaseException
) -> None:
    msg = "A plugin raised an exception during an old-style hookwrapper teardown.\n"
    msg += f"Plugin: {hook_impl.plugin_name}, Hook: {hook_name}\n"
    msg += f"{type(e).__name__}: {e}\n"
    msg += "For more information see https://pluggy.readthedocs.io/en/stable/api_reference.html#pluggy.PluggyTeardownRaisedWarning"  # noqa: E501
    warnings.warn(PluggyTeardownRaisedWarning(msg), stacklevel=7)


def _multicall(
    hook_name: str,
    normal_impls: Sequence[HookImpl],
    wrapper_impls: Sequence[WrapperImpl],
    caller_kwargs: Mapping[str, object],
    firstresult: bool,
    async_submitter: Submitter,
) -> object | list[object]:
    """Execute a call into multiple python functions/methods and return the
    result(s).

    ``caller_kwargs`` comes from HookCaller.__call__().
    """
    __tracebackhide__ = True
    results: list[object] = []
    exception = None

    # Set up wrapper completion hooks
    from ._hook_callers import CompletionHook

    completion_hooks: list[CompletionHook] = []

    try:
        # Set up all wrappers and collect their completion hooks
        for wrapper_impl in reversed(wrapper_impls):
            completion_hook = wrapper_impl.setup_and_get_completion_hook(
                hook_name, caller_kwargs
            )
            completion_hooks.append(completion_hook)

        # Process normal implementations (in reverse order for correct execution)
        # Caller ensures normal_impls contains only non-wrapper implementations
        for normal_impl in reversed(normal_impls):
            args = normal_impl._get_call_args(caller_kwargs)
            res = normal_impl.function(*args)
            if res is not None:
                # Handle awaitable results using maybe_submit
                if isinstance(res, Awaitable):
                    res = async_submitter.maybe_submit(res)
                results.append(res)
                if firstresult:  # halt further impl calls
                    break
    except BaseException as exc:
        exception = exc

    # Determine final result before teardown
    if firstresult:  # first result hooks return a single value
        result = results[0] if results else None
    else:
        result = results

    # Run completion hooks in reverse order (LIFO - Last In, First Out)
    for completion_hook in reversed(completion_hooks):
        result, exception = completion_hook(result, exception)

    if exception is not None:
        raise exception
    else:
        return result
