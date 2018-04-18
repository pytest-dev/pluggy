"""
Legacy hook caller
"""
from .utils import HookCallError, _raise_wrapfail, _Result


def _wrapped_call(wrap_controller, func):
    """ Wrap calling to a function with a generator which needs to yield
    exactly once.  The yield point will trigger calling the wrapped function
    and return its ``_Result`` to the yield point.  The generator then needs
    to finish (raise StopIteration) in order for the wrapped call to complete.
    """
    try:
        next(wrap_controller)   # first yield
    except StopIteration:
        _raise_wrapfail(wrap_controller, "did not yield")
    call_outcome = _Result.from_call(func)
    try:
        wrap_controller.send(call_outcome)
        _raise_wrapfail(wrap_controller, "has second yield")
    except StopIteration:
        pass
    return call_outcome.get_result()


class _LegacyMultiCall(object):
    """ execute a call into multiple python functions/methods. """

    # XXX note that the __multicall__ argument is supported only
    # for pytest compatibility reasons.  It was never officially
    # supported there and is explicitely deprecated since 2.8
    # so we can remove it soon, allowing to avoid the below recursion
    # in execute() and simplify/speed up the execute loop.

    def __init__(self, hook_impls, kwargs, firstresult=False):
        self.hook_impls = hook_impls
        self.caller_kwargs = kwargs  # come from _HookCaller.__call__()
        self.caller_kwargs["__multicall__"] = self
        self.firstresult = firstresult

    def execute(self):
        caller_kwargs = self.caller_kwargs
        self.results = results = []
        firstresult = self.firstresult

        while self.hook_impls:
            hook_impl = self.hook_impls.pop()
            try:
                args = [caller_kwargs[argname] for argname in hook_impl.argnames]
            except KeyError:
                for argname in hook_impl.argnames:
                    if argname not in caller_kwargs:
                        raise HookCallError(
                            "hook call must provide argument %r" % (argname,))
            if hook_impl.hookwrapper:
                return _wrapped_call(hook_impl.function(*args), self.execute)
            res = hook_impl.function(*args)
            if res is not None:
                if firstresult:
                    return res
                results.append(res)

        if not firstresult:
            return results

    def __repr__(self):
        status = "%d meths" % (len(self.hook_impls),)
        if hasattr(self, "results"):
            status = ("%d results, " % len(self.results)) + status
        return "<_MultiCall %s, kwargs=%r>" % (status, self.caller_kwargs)


def _legacymulticall(hook_impls, caller_kwargs, firstresult=False):
    return _LegacyMultiCall(
        hook_impls, caller_kwargs, firstresult=firstresult).execute()
