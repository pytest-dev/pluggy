"""
Call loop machinery
"""
from ._result import Result


def _multicall(hook_name, wrappers, non_wrappers, caller_kwargs, firstresult):
    """Execute a call into multiple python functions/methods and return the
    result(s).

    ``caller_kwargs`` comes from _HookCaller.__call__().
    """
    __tracebackhide__ = True
    results = []
    excinfo = None
    teardowns = []
    try:
        for wrapper in reversed(wrappers):
            teardowns.append(wrapper(caller_kwargs))
        for hook_impl in reversed(non_wrappers):
            res = hook_impl(caller_kwargs)
            if res is not None:
                results.append(res)
                if firstresult:  # halt further impl calls
                    break
    except BaseException as e:
        excinfo = e

    if firstresult:  # first result hooks return a single value
        outcome = Result(results[0] if results else None, excinfo)
    else:
        outcome = Result(results, excinfo)

    # run all wrapper post-yield blocks
    for cleanup in reversed(teardowns):

        cleanup(outcome)

    return outcome.get_result()
