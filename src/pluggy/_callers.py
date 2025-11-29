"""
Call loop machinery
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence

from ._hooks import _NormalHookImplementation
from ._hooks import _WrapperHookImplementation
from ._hooks import Teardown


def _multicall(
    hook_name: str,
    normal_impls: Sequence[_NormalHookImplementation],
    wrapper_impls: Sequence[_WrapperHookImplementation],
    caller_kwargs: Mapping[str, object],
    firstresult: bool,
) -> object | list[object]:
    """Execute a call into multiple python functions/methods and return the
    result(s).

    ``caller_kwargs`` comes from HookCaller.__call__().
    """
    __tracebackhide__ = True
    results: list[object] = []
    exception = None
    teardowns: list[Teardown] = []

    try:
        # Phase 1: Run wrapper setup (in reverse - tryfirst wrappers run first)
        for wrapper in reversed(wrapper_impls):
            teardowns.append(wrapper.setup_teardown(caller_kwargs))

        # Phase 2: Run normal impls (in reverse - tryfirst impls run first)
        for impl in reversed(normal_impls):
            res = impl.call(caller_kwargs)
            if res is not None:
                results.append(res)
                if firstresult:  # halt further impl calls
                    break

    except BaseException as exc:
        exception = exc

    # Compute result before teardowns
    if firstresult:
        outcome: object = results[0] if results else None
    else:
        outcome = results

    # Run all wrapper teardowns in reverse order
    for teardown in reversed(teardowns):
        outcome, exception = teardown(outcome, exception)

    if exception is not None:
        raise exception
    return outcome
