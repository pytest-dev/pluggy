import inspect
import sys
from typing import Tuple, cast

_PYPY = hasattr(sys, "pypy_version_info")


def varnames(func: object) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Return tuple of positional and keywrord argument names for a function,
    method, class or callable.

    In case of a class, its ``__init__`` method is considered.
    For methods the ``self`` parameter is not included.
    """
    if inspect.isclass(func):
        try:
            func = getattr(func, "__init__")
        except AttributeError:
            return (), ()
    elif not inspect.isroutine(func):  # callable object?
        try:
            func = getattr(func, "__call__", func)
        except Exception:
            return (), ()
    spec: inspect.FullArgSpec
    try:  # func MUST be a function or method here or we won't parse any args
        spec = inspect.getfullargspec(func)
    except TypeError:
        return (), ()

    args: Tuple[str, ...] = tuple(spec.args)  # type: ignore

    if spec.defaults is not None:  # type: ignore
        index = -len(spec.defaults)  # type: ignore
        args, kwargs = args[:index], args[index:]
    else:
        kwargs = ()

    # strip any implicit instance arg
    # pypy3 uses "obj" instead of "self" for default dunder methods
    implicit_names = ("self",) if not _PYPY else ("self", "obj")
    if args:
        if inspect.ismethod(func) or (
            "." in cast(str, getattr(func, "__qualname__", ""))
            and args[0] in implicit_names
        ):
            args = args[1:]

    return args, kwargs
