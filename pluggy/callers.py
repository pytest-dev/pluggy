'''
Call loop machinery
'''
import sys


_py3 = sys.version_info > (3, 0)


if not _py3:
    exec("""
def _reraise(cls, val, tb):
    raise cls, val, tb
""")


def _raise_wrapfail(wrap_controller, msg):
    co = wrap_controller.gi_code
    raise RuntimeError("wrap_controller at %r %s:%d %s" %
                       (co.co_name, co.co_filename, co.co_firstlineno, msg))


class HookCallError(Exception):
    """ Hook was called wrongly. """


class _Result(object):
    def __init__(self, result, excinfo):
        self.result = result
        self.excinfo = excinfo

    @classmethod
    def from_call(cls, func):
        __tracebackhide__ = True
        result = excinfo = None
        try:
            result = func()
        except BaseException:
            excinfo = sys.exc_info()

        return cls(result, excinfo)

    def force_result(self, result):
        self.result = result
        self.excinfo = None

    def get_result(self):
        __tracebackhide__ = True
        if self.excinfo is None:
            return self.result
        else:
            ex = self.excinfo
            if _py3:
                raise ex[1].with_traceback(ex[2])
            _reraise(*ex)  # noqa


class _MultiCall(object):
    """Execute a call into multiple python functions/methods.
    """
    def __init__(self, hook_impls, kwargs, specopts={}, hook=None):
        self.hook = hook
        self.hook_impls = hook_impls
        self.caller_kwargs = kwargs  # come from _HookCaller.__call__()
        self.specopts = hook.spec_opts if hook else specopts

    def execute(self):
        __tracebackhide__ = True
        caller_kwargs = self.caller_kwargs
        self.results = results = []
        firstresult = self.specopts.get("firstresult")
        excinfo = None
        try:  # run impl and wrapper setup functions in a loop
            teardowns = []
            try:
                for hook_impl in reversed(self.hook_impls):
                    try:
                        args = [caller_kwargs[argname] for argname in hook_impl.argnames]
                        # args = operator.itemgetter(hookimpl.argnames)(caller_kwargs)
                    except KeyError:
                        for argname in hook_impl.argnames:
                            if argname not in caller_kwargs:
                                raise HookCallError(
                                    "hook call must provide argument %r" % (argname,))

                    if hook_impl.hookwrapper:
                        try:
                            gen = hook_impl.function(*args)
                            next(gen)   # first yield
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
        finally:
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

    def __repr__(self):
        status = "%d meths" % (len(self.hook_impls),)
        if hasattr(self, "results"):
            status = ("%d results, " % len(self.results)) + status
        return "<_MultiCall %s, kwargs=%r>" % (status, self.caller_kwargs)
