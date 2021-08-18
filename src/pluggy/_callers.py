"""
Call loop machinery
"""
import sys

from ._result import (
    HookCallError,
    _Result,
    WrapResult,
    _raise_wrapfail,
    EXCINFO,
    SomeResult,
)
from typing import List, TYPE_CHECKING, Dict, cast, overload, Union, Callable
from typing_extensions import Literal

if TYPE_CHECKING:
    from ._hooks import HookImpl

HookImpls = List["HookImpl"]
HookArgs = Dict[str, object]
HookResultCallback = Callable[[SomeResult], SomeResult]
HookExecCallable = Callable[
    [str, List["HookImpl"], Dict[str, object], bool],
    Union[SomeResult, List[SomeResult]],
]


@overload
def _multicall(
    hook_name: str,
    hook_impls: HookImpls,
    caller_kwargs: HookArgs,
    firstresult: Literal[False],
) -> List[SomeResult]:
    pass


@overload
def _multicall(
    hook_name: str,
    hook_impls: HookImpls,
    caller_kwargs: HookArgs,
    firstresult: Literal[True],
) -> SomeResult:
    pass


def _multicall(
    hook_name: str,
    hook_impls: HookImpls,
    caller_kwargs: HookArgs,
    firstresult: bool,
) -> Union[List[SomeResult], SomeResult]:
    """Execute a call into multiple python functions/methods and return the
    result(s).

    ``caller_kwargs`` comes from _HookCaller.__call__().
    """
    __tracebackhide__ = True
    results = []
    excinfo = None, None, None  # type: EXCINFO
    teardowns: List[WrapResult] = []
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
                    gen = cast(WrapResult, hook_impl.function(*args))
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
        excinfo = sys.exc_info()
    if firstresult:  # first result hooks return a single value
        outcome = _Result(results[0] if results else None, excinfo)
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
