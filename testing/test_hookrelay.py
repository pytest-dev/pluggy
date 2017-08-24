import pytest
from pluggy import PluginValidationError, HookimplMarker, HookspecMarker


hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


def test_happypath(pm):
    class Api(object):
        @hookspec
        def hello(self, arg):
            "api hook 1"

    pm.add_hookspecs(Api)
    hook = pm.hook
    assert hasattr(hook, 'hello')
    assert repr(hook.hello).find("hello") != -1

    class Plugin(object):
        @hookimpl
        def hello(self, arg):
            return arg + 1

    plugin = Plugin()
    pm.register(plugin)
    l = hook.hello(arg=3)
    assert l == [4]
    assert not hasattr(hook, 'world')
    pm.unregister(plugin)
    assert hook.hello(arg=3) == []


def test_argmismatch(pm):
    class Api(object):
        @hookspec
        def hello(self, arg):
            "api hook 1"

    pm.add_hookspecs(Api)

    class Plugin(object):
        @hookimpl
        def hello(self, argwrong):
            pass

    with pytest.raises(PluginValidationError) as exc:
        pm.register(Plugin())

    assert "argwrong" in str(exc.value)


def test_only_kwargs(pm):
    class Api(object):
        @hookspec
        def hello(self, arg):
            "api hook 1"

    pm.add_hookspecs(Api)
    with pytest.raises(TypeError) as exc:
        pm.hook.hello(3)

    comprehensible = "hook calling supports only keyword arguments"
    assert comprehensible in str(exc.value)


def test_firstresult_definition(pm):
    class Api(object):
        @hookspec(firstresult=True)
        def hello(self, arg):
            "api hook 1"

    pm.add_hookspecs(Api)

    class Plugin1(object):
        @hookimpl
        def hello(self, arg):
            return arg + 1

    class Plugin2(object):
        @hookimpl
        def hello(self, arg):
            return arg - 1

    class Plugin3(object):
        @hookimpl
        def hello(self, arg):
            return None

    pm.register(Plugin1())  # discarded - not the last registered plugin
    pm.register(Plugin2())  # used as result
    pm.register(Plugin3())  # None result is ignored
    res = pm.hook.hello(arg=3)
    assert res == 2
