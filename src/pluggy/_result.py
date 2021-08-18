"""
Hook wrapper "result" utilities.
"""
import sys
from typing import Callable, NoReturn, Union, Tuple, Type, Optional, Generator
from types import TracebackType


SomeResult = Optional[object]
WrapResult = Generator[None, "_Result", None]
HookFunction = Callable[..., Union[SomeResult, WrapResult]]
EXCINFO = Union[
    Tuple[Type[BaseException], BaseException, TracebackType], Tuple[None, None, None]
]


def _raise_wrapfail(wrap_controller: WrapResult, msg: str) -> NoReturn:
    co = wrap_controller.gi_code
    raise RuntimeError(
        "wrap_controller at %r %s:%d %s"
        % (co.co_name, co.co_filename, co.co_firstlineno, msg)
    )


class HookCallError(Exception):
    """Hook was called wrongly."""


class _Result:
    result: SomeResult
    _excinfo: EXCINFO

    def __init__(self, result: Optional[object], excinfo: EXCINFO):
        self._result = result
        self._excinfo = excinfo

    @property
    def excinfo(self) -> Optional[EXCINFO]:
        if self._excinfo[0] is not None:
            return self._excinfo
        else:
            return None

    @classmethod
    def from_call(cls, func: HookFunction) -> "_Result":
        __tracebackhide__ = True
        result = None
        excinfo: EXCINFO = None, None, None
        try:
            result = func()
        except BaseException:
            excinfo = sys.exc_info()

        return cls(result, excinfo)

    def force_result(self, result: SomeResult) -> None:
        """Force the result(s) to ``result``.

        If the hook was marked as a ``firstresult`` a single value should
        be set otherwise set a (modified) list of results. Any exceptions
        found during invocation will be deleted.
        """
        self._result = result
        self._excinfo = None, None, None

    def get_result(self) -> SomeResult:
        """Get the result(s) for this hook call.

        If the hook was marked as a ``firstresult`` only a single value
        will be returned otherwise a list of results.
        """
        __tracebackhide__ = True
        if self._excinfo[0] is None:
            return self._result
        else:
            ex = self._excinfo
            raise ex[1].with_traceback(ex[2])
