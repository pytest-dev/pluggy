import inspect


def varnames(func):
    """Return tuple of positional and keywrord argument names for a function,
    method, class or callable.

    In case of a class, its ``__init__`` method is considered.
    For methods the ``self`` parameter is not included.
    """
    cache = getattr(func, "__dict__", {})
    try:
        return cache["_varnames"]
    except KeyError:
        pass

    if inspect.isclass(func):
        try:
            func = func.__init__
        except AttributeError:
            return (), ()
    elif not inspect.isroutine(func):  # callable object?
        try:
            func = getattr(func, '__call__', func)
        except Exception:
            return ()

    try:  # func MUST be a function or method here or we won't parse any args
        spec = inspect.getargspec(func)
    except TypeError:
        return (), ()

    args, defaults = tuple(spec.args), spec.defaults
    if defaults:
        index = -len(defaults)
        args, defaults = args[:index], tuple(args[index:])
    else:
        defaults = ()

    # strip any implicit instance arg
    if args:
        if inspect.ismethod(func) or (
            '.' in getattr(func, '__qualname__', ()) and args[0] == 'self'
        ):
            args = args[1:]

    assert "self" not in args  # best naming practises check?
    try:
        cache["_varnames"] = args, defaults
    except TypeError:
        pass
    return args, defaults


if hasattr(inspect, 'signature'):
    def _formatdef(func):
        return "%s%s" % (
            func.__name__,
            str(inspect.signature(func))
        )
else:
    def _formatdef(func):
        return "%s%s" % (
            func.__name__,
            inspect.formatargspec(*inspect.getargspec(func))
        )
