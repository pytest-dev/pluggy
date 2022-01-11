"""
Call loop machinery
"""
import sys
from typing import cast, Generator, List, Mapping, Sequence, Union
from typing import TYPE_CHECKING

from ._result import HookCallError, _Result, _raise_wrapfail

if TYPE_CHECKING:
    from ._hooks import HookImpl


def _multicall(
    hook_name: str,
    hook_impls: Sequence["HookImpl"],
    caller_kwargs: Mapping[str, object],
    firstresult: bool,
) -> Union[object, List[object]]:
    """Execute a call into multiple python functions/methods and return the
    result(s).

    ``caller_kwargs`` comes from _HookCaller.__call__().
    """
    __tracebackhide__ = True
    results: List[object] = []
    excinfo = None
    try:  # run impl and wrapper setup functions in a loop
        teardowns = []
        try:
            for hook_impl in reversed(hook_impls):
                try:
                    args = [caller_kwargs[argname] for argname in hook_impl.argnames]
                except KeyError:
                    for argname in hook_impl.argnames:
                        if argname not in caller_kwargs:
                            raise HookCallError(
                                f"hook call must provide argument {argname!r}"
                            )

                if hook_impl.hookwrapper:
                    try:
                        # If this cast is not valid, a type error is raised below,
                        # which is the desired response.
                        res = hook_impl.function(*args)
                        gen = cast(Generator[None, _Result[object], None], res)
                        next(gen)  # first yield
                        teardowns.append(gen)
                    except StopIteration:
                        _raise_wrapfail(gen, "did not yield")
                else:
                    res = hook_impl.function(*args)
                    if res is not None:
                        results.append(res)
                        if firstresult:  # halt further impl calls
                            break
        except BaseException:
            _excinfo = sys.exc_info()
            assert _excinfo[0] is not None
            assert _excinfo[1] is not None
            assert _excinfo[2] is not None
            excinfo = (_excinfo[0], _excinfo[1], _excinfo[2])
    finally:
        if firstresult:  # first result hooks return a single value
            outcome: _Result[Union[object, List[object]]] = _Result(
                results[0] if results else None, excinfo
            )
        else:
            outcome = _Result(results, excinfo)

        # run all wrapper post-yield blocks
        for gen in reversed(teardowns):
            try:
                gen.send(outcome)
                _raise_wrapfail(gen, "has second yield")
            except StopIteration:
                pass

        return outcome.get_result()
