"""
Hook wrapper "result" utilities.
"""
from types import TracebackType
from typing import final, Optional, Callable, Tuple, Type


def _raise_wrapfail(wrap_controller, msg):
    co = wrap_controller.gi_code
    raise RuntimeError(
        "wrap_controller at %r %s:%d %s"
        % (co.co_name, co.co_filename, co.co_firstlineno, msg)
    )


@final
class Result:
    _result: Optional[object]
    _exc: Optional[BaseException]

    def __init__(self, result: Optional[object], excinfo: Optional[BaseException]):
        self._result = result
        self._exc = excinfo

    @property
    def excinfo(
        self,
    ) -> Optional[Tuple[Type[BaseException], BaseException, Optional[TracebackType]]]:
        e = self._exc
        if e is None:
            return None
        return type(e), e, e.__traceback__

    @staticmethod
    def from_call(func: Callable[[], object]) -> "Result":
        __tracebackhide__ = True
        try:
            return Result(func(), None)
        except BaseException as e:
            return Result(None, e)

    def force_result(self, result: object):
        """Force the result(s) to ``result``.

        If the hook was marked as a ``firstresult`` a single value should
        be set otherwise set a (modified) list of results. Any exceptions
        found during invocation will be deleted.
        """
        self._result = result
        self._exc = None

    def get_result(self) -> object:
        """Get the result(s) for this hook call.

        If the hook was marked as a ``firstresult`` only a single value
        will be returned otherwise a list of results.
        """
        __tracebackhide__ = True
        if self._exc is None:
            return self._result
        else:
            ex = self._exc
            raise ex.with_traceback(ex.__traceback__)
