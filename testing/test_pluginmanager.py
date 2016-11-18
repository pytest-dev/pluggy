import pytest

from pluggy import (PluginValidationError,
                    HookCallError, HookimplMarker, HookspecMarker)


hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


def test_plugin_double_register(pm):
    pm.register(42, name="abc")
    with pytest.raises(ValueError):
        pm.register(42, name="abc")
    with pytest.raises(ValueError):
        pm.register(42, name="def")


def test_pm(pm):
    class A:
        pass

    a1, a2 = A(), A()
    pm.register(a1)
    assert pm.is_registered(a1)
    pm.register(a2, "hello")
    assert pm.is_registered(a2)
    l = pm.get_plugins()
    assert a1 in l
    assert a2 in l
    assert pm.get_plugin('hello') == a2
    assert pm.unregister(a1) == a1
    assert not pm.is_registered(a1)

    l = pm.list_name_plugin()
    assert len(l) == 1
    assert l == [("hello", a2)]


def test_has_plugin(pm):
    class A:
        pass

    a1 = A()
    pm.register(a1, 'hello')
    assert pm.is_registered(a1)
    assert pm.has_plugin('hello')


def test_register_dynamic_attr(he_pm):
    class A:
        def __getattr__(self, name):
            if name[0] != "_":
                return 42
            raise AttributeError()

    a = A()
    he_pm.register(a)
    assert not he_pm.get_hookcallers(a)


def test_pm_name(pm):
    class A:
        pass

    a1 = A()
    name = pm.register(a1, name="hello")
    assert name == "hello"
    pm.unregister(a1)
    assert pm.get_plugin(a1) is None
    assert not pm.is_registered(a1)
    assert not pm.get_plugins()
    name2 = pm.register(a1, name="hello")
    assert name2 == name
    pm.unregister(name="hello")
    assert pm.get_plugin(a1) is None
    assert not pm.is_registered(a1)
    assert not pm.get_plugins()


def test_set_blocked(pm):
    class A:
        pass

    a1 = A()
    name = pm.register(a1)
    assert pm.is_registered(a1)
    assert not pm.is_blocked(name)
    pm.set_blocked(name)
    assert pm.is_blocked(name)
    assert not pm.is_registered(a1)

    pm.set_blocked("somename")
    assert pm.is_blocked("somename")
    assert not pm.register(A(), "somename")
    pm.unregister(name="somename")
    assert pm.is_blocked("somename")


def test_register_mismatch_method(he_pm):
    class hello:
        @hookimpl
        def he_method_notexists(self):
            pass

    he_pm.register(hello())
    with pytest.raises(PluginValidationError):
        he_pm.check_pending()


def test_register_mismatch_arg(he_pm):
    class hello:
        @hookimpl
        def he_method1(self, qlwkje):
            pass

    with pytest.raises(PluginValidationError):
        he_pm.register(hello())


def test_register(pm):
    class MyPlugin:
        pass
    my = MyPlugin()
    pm.register(my)
    assert my in pm.get_plugins()
    my2 = MyPlugin()
    pm.register(my2)
    assert set([my, my2]).issubset(pm.get_plugins())

    assert pm.is_registered(my)
    assert pm.is_registered(my2)
    pm.unregister(my)
    assert not pm.is_registered(my)
    assert my not in pm.get_plugins()


def test_register_unknown_hooks(pm):
    class Plugin1:
        @hookimpl
        def he_method1(self, arg):
            return arg + 1

    pname = pm.register(Plugin1())

    class Hooks:
        @hookspec
        def he_method1(self, arg):
            pass

    pm.add_hookspecs(Hooks)
    # assert not pm._unverified_hooks
    assert pm.hook.he_method1(arg=1) == [2]
    assert len(pm.get_hookcallers(pm.get_plugin(pname))) == 1


def test_register_historic(pm):
    class Hooks:
        @hookspec(historic=True)
        def he_method1(self, arg):
            pass
    pm.add_hookspecs(Hooks)

    pm.hook.he_method1.call_historic(kwargs=dict(arg=1))
    l = []

    class Plugin:
        @hookimpl
        def he_method1(self, arg):
            l.append(arg)

    pm.register(Plugin())
    assert l == [1]

    class Plugin2:
        @hookimpl
        def he_method1(self, arg):
            l.append(arg * 10)

    pm.register(Plugin2())
    assert l == [1, 10]
    pm.hook.he_method1.call_historic(kwargs=dict(arg=12))
    assert l == [1, 10, 120, 12]


def test_with_result_memorized(pm):
    class Hooks:
        @hookspec(historic=True)
        def he_method1(self, arg):
            pass
    pm.add_hookspecs(Hooks)

    he_method1 = pm.hook.he_method1
    he_method1.call_historic(lambda res: l.append(res), dict(arg=1))
    l = []

    class Plugin:
        @hookimpl
        def he_method1(self, arg):
            return arg * 10

    pm.register(Plugin())
    assert l == [10]


def test_with_callbacks_immediately_executed(pm):
    class Hooks:
        @hookspec(historic=True)
        def he_method1(self, arg):
            pass
    pm.add_hookspecs(Hooks)

    class Plugin1:
        @hookimpl
        def he_method1(self, arg):
            return arg * 10

    class Plugin2:
        @hookimpl
        def he_method1(self, arg):
            return arg * 20

    class Plugin3:
        @hookimpl
        def he_method1(self, arg):
            return arg * 30

    l = []
    pm.register(Plugin1())
    pm.register(Plugin2())

    he_method1 = pm.hook.he_method1
    he_method1.call_historic(lambda res: l.append(res), dict(arg=1))
    assert l == [20, 10]
    pm.register(Plugin3())
    assert l == [20, 10, 30]


def test_register_historic_incompat_hookwrapper(pm):
    class Hooks:
        @hookspec(historic=True)
        def he_method1(self, arg):
            pass

    pm.add_hookspecs(Hooks)

    l = []

    class Plugin:
        @hookimpl(hookwrapper=True)
        def he_method1(self, arg):
            l.append(arg)

    with pytest.raises(PluginValidationError):
        pm.register(Plugin())


def test_call_extra(pm):
    class Hooks:
        @hookspec
        def he_method1(self, arg):
            pass

    pm.add_hookspecs(Hooks)

    def he_method1(arg):
        return arg * 10

    l = pm.hook.he_method1.call_extra([he_method1], dict(arg=1))
    assert l == [10]


def test_call_with_too_few_args(pm):
    class Hooks:
        @hookspec
        def he_method1(self, arg):
            pass

    pm.add_hookspecs(Hooks)

    class Plugin1:
        @hookimpl
        def he_method1(self, arg):
            0 / 0
    pm.register(Plugin1())
    with pytest.raises(HookCallError):
        pm.hook.he_method1()


def test_subset_hook_caller(pm):
    class Hooks:
        @hookspec
        def he_method1(self, arg):
            pass

    pm.add_hookspecs(Hooks)

    l = []

    class Plugin1:
        @hookimpl
        def he_method1(self, arg):
            l.append(arg)

    class Plugin2:
        @hookimpl
        def he_method1(self, arg):
            l.append(arg * 10)

    class PluginNo:
        pass

    plugin1, plugin2, plugin3 = Plugin1(), Plugin2(), PluginNo()
    pm.register(plugin1)
    pm.register(plugin2)
    pm.register(plugin3)
    pm.hook.he_method1(arg=1)
    assert l == [10, 1]
    l[:] = []

    hc = pm.subset_hook_caller("he_method1", [plugin1])
    hc(arg=2)
    assert l == [20]
    l[:] = []

    hc = pm.subset_hook_caller("he_method1", [plugin2])
    hc(arg=2)
    assert l == [2]
    l[:] = []

    pm.unregister(plugin1)
    hc(arg=2)
    assert l == []
    l[:] = []

    pm.hook.he_method1(arg=1)
    assert l == [10]


def test_add_hookspecs_nohooks(pm):
    with pytest.raises(ValueError):
        pm.add_hookspecs(10)
