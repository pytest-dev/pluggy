from pluggy import PluginManager, HookimplMarker, HookspecMarker


hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


def test_parse_hookimpl_override():
    class MyPluginManager(PluginManager):
        def parse_hookimpl_opts(self, module_or_class, name):
            opts = PluginManager.parse_hookimpl_opts(
                self, module_or_class, name)
            if opts is None:
                if name.startswith("x1"):
                    opts = {}
            return opts

    class Plugin:
        def x1meth(self):
            pass

        @hookimpl(hookwrapper=True, tryfirst=True)
        def x1meth2(self):
            pass

    class Spec:
        @hookspec
        def x1meth(self):
            pass

        @hookspec
        def x1meth2(self):
            pass

    pm = MyPluginManager(hookspec.project_name)
    pm.register(Plugin())
    pm.add_hookspecs(Spec)
    assert not pm.hook.x1meth._nonwrappers[0].hookwrapper
    assert not pm.hook.x1meth._nonwrappers[0].tryfirst
    assert not pm.hook.x1meth._nonwrappers[0].trylast
    assert not pm.hook.x1meth._nonwrappers[0].optionalhook

    assert pm.hook.x1meth2._wrappers[0].tryfirst
    assert pm.hook.x1meth2._wrappers[0].hookwrapper


def test_plugin_getattr_raises_errors():
    """Pluggy must be able to handle plugins which raise weird exceptions
    when getattr() gets called (#11).
    """
    class DontTouchMe:
        def __getattr__(self, x):
            raise Exception('cant touch me')

    class Module:
        pass

    module = Module()
    module.x = DontTouchMe()

    pm = PluginManager(hookspec.project_name)
    # register() would raise an error
    pm.register(module, 'donttouch')
    assert pm.get_plugin('donttouch') is module
