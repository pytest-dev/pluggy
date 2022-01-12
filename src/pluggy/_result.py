"""
Hook wrapper "result" utilities.
"""
import sys
from types import TracebackType
from typing import (
    Callable,
    cast,
    Generator,
    Generic,
    Optional,
    Tuple,
    Type,
    TYPE_CHECKING,
    TypeVar,
)

if TYPE_CHECKING:
    from typing import NoReturn


_ExcInfo = Tuple[Type[BaseException], BaseException, TracebackType]
_T = TypeVar("_T")


def _raise_wrapfail(
    wrap_controller: Generator[None, "_Result[_T]", None], msg: str
) -> "NoReturn":
    co = wrap_controller.gi_code
    raise RuntimeError(
        "wrap_controller at %r %s:%d %s"
        % (co.co_name, co.co_filename, co.co_firstlineno, msg)
    )


class HookCallError(Exception):
    """Hook was called wrongly."""


class _Result(Generic[_T]):
    __slots__ = ("_result", "_excinfo")

    def __init__(self, result: Optional[_T], excinfo: Optional[_ExcInfo]) -> None:
        self._result = result
        self._excinfo = excinfo

    @property
    def excinfo(self) -> Optional[_ExcInfo]:
        return self._excinfo

    @classmethod
    def from_call(cls, func: Callable[[], _T]) -> "_Result[_T]":
        __tracebackhide__ = True
        result = excinfo = None
        try:
            result = func()
        except BaseException:
            _excinfo = sys.exc_info()
            assert _excinfo[0] is not None
            assert _excinfo[1] is not None
            assert _excinfo[2] is not None
            excinfo = (_excinfo[0], _excinfo[1], _excinfo[2])

        return cls(result, excinfo)

    def force_result(self, result: _T) -> None:
        """Force the result(s) to ``result``.

        If the hook was marked as a ``firstresult`` a single value should
        be set otherwise set a (modified) list of results. Any exceptions
        found during invocation will be deleted.
        """
        self._result = result
        self._excinfo = None

    def get_result(self) -> _T:
        """Get the result(s) for this hook call.

        If the hook was marked as a ``firstresult`` only a single value
        will be returned otherwise a list of results.
        """
        __tracebackhide__ = True
        if self._excinfo is None:
            return cast(_T, self._result)
        else:
            ex = self._excinfo
            raise ex[1].with_traceback(ex[2])
