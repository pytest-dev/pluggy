"""
Deprecation warnings testing roundup.
"""
import pytest
from pluggy import HookimplMarker, HookspecMarker

hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


def test_callhistoric_proc_deprecated(pm):
    """``proc`` kwarg to `PluginMananger.call_historic()` is now officially
    deprecated.
    """

    class P1(object):
        @hookspec(historic=True)
        @hookimpl
        def m(self, x):
            pass

    p1 = P1()
    pm.add_hookspecs(p1)
    pm.register(p1)
    with pytest.deprecated_call():
        pm.hook.m.call_historic(kwargs=dict(x=10), proc=lambda res: res)
