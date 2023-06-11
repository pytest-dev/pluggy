"""
Call loop machinery
"""
from typing import cast
from typing import Generator
from typing import List
from typing import Mapping
from typing import Sequence
from typing import TYPE_CHECKING
from typing import Union

from ._result import _raise_wrapfail
from ._result import _Result
from ._result import HookCallError

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
    exception = None
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
        except BaseException as exc:
            exception = exc
    finally:
        if firstresult:  # first result hooks return a single value
            outcome: _Result[Union[object, List[object]]] = _Result(
                results[0] if results else None, exception
            )
        else:
            outcome = _Result(results, exception)

        # run all wrapper post-yield blocks
        for gen in reversed(teardowns):
            try:
                gen.send(outcome)
                _raise_wrapfail(gen, "has second yield")
            except StopIteration:
                pass

        return outcome.get_result()
