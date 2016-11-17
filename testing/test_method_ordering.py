import pytest


import sys
import types

from pluggy import PluginManager, HookImpl, HookimplMarker, HookspecMarker

hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


@pytest.fixture
def hc(pm):
    class Hooks(object):
        @hookspec
        def he_method1(self, arg):
            pass
    pm.add_hookspecs(Hooks)
    return pm.hook.he_method1


@pytest.fixture
def addmeth(hc):
    def addmeth(tryfirst=False, trylast=False, hookwrapper=False):
        def wrap(func):
            hookimpl(tryfirst=tryfirst, trylast=trylast,
                     hookwrapper=hookwrapper)(func)
            hc._add_hookimpl(HookImpl(None, "<temp>", func, func.example_impl))
            return func
        return wrap
    return addmeth


def funcs(hookmethods):
    return [hookmethod.function for hookmethod in hookmethods]


def test_adding_nonwrappers(hc, addmeth):
    @addmeth()
    def he_method1():
        pass

    @addmeth()
    def he_method2():
        pass

    @addmeth()
    def he_method3():
        pass
    assert funcs(hc._nonwrappers) == [he_method1, he_method2, he_method3]


def test_adding_nonwrappers_trylast(hc, addmeth):
    @addmeth()
    def he_method1_middle():
        pass

    @addmeth(trylast=True)
    def he_method1():
        pass

    @addmeth()
    def he_method1_b():
        pass
    assert funcs(hc._nonwrappers) == [he_method1, he_method1_middle, he_method1_b]


def test_adding_nonwrappers_trylast3(hc, addmeth):
    @addmeth()
    def he_method1_a():
        pass

    @addmeth(trylast=True)
    def he_method1_b():
        pass

    @addmeth()
    def he_method1_c():
        pass

    @addmeth(trylast=True)
    def he_method1_d():
        pass
    assert funcs(hc._nonwrappers) == \
        [he_method1_d, he_method1_b, he_method1_a, he_method1_c]


def test_adding_nonwrappers_trylast2(hc, addmeth):
    @addmeth()
    def he_method1_middle():
        pass

    @addmeth()
    def he_method1_b():
        pass

    @addmeth(trylast=True)
    def he_method1():
        pass
    assert funcs(hc._nonwrappers) == \
        [he_method1, he_method1_middle, he_method1_b]


def test_adding_nonwrappers_tryfirst(hc, addmeth):
    @addmeth(tryfirst=True)
    def he_method1():
        pass

    @addmeth()
    def he_method1_middle():
        pass

    @addmeth()
    def he_method1_b():
        pass
    assert funcs(hc._nonwrappers) == [
        he_method1_middle, he_method1_b, he_method1]


def test_adding_wrappers_ordering(hc, addmeth):
    @addmeth(hookwrapper=True)
    def he_method1():
        pass

    @addmeth()
    def he_method1_middle():
        pass

    @addmeth(hookwrapper=True)
    def he_method3():
        pass

    assert funcs(hc._nonwrappers) == [he_method1_middle]
    assert funcs(hc._wrappers) == [he_method1, he_method3]


def test_adding_wrappers_ordering_tryfirst(hc, addmeth):
    @addmeth(hookwrapper=True, tryfirst=True)
    def he_method1():
        pass

    @addmeth(hookwrapper=True)
    def he_method2():
        pass

    assert hc._nonwrappers == []
    assert funcs(hc._wrappers) == [he_method2, he_method1]


def test_hookspec(pm):
    class HookSpec(object):
        @hookspec()
        def he_myhook1(arg1):
            pass

        @hookspec(firstresult=True)
        def he_myhook2(arg1):
            pass

        @hookspec(firstresult=False)
        def he_myhook3(arg1):
            pass

    pm.add_hookspecs(HookSpec)
    assert not pm.hook.he_myhook1.spec.opts["firstresult"]
    assert pm.hook.he_myhook2.spec.opts["firstresult"]
    assert not pm.hook.he_myhook3.spec.opts["firstresult"]


@pytest.mark.parametrize('name', ["hookwrapper", "optionalhook", "tryfirst", "trylast"])
@pytest.mark.parametrize('val', [True, False])
def test_hookimpl(name, val):
    @hookimpl(**{name: val})
    def he_myhook1(arg1):
        pass
    if val:
        assert he_myhook1.example_impl.get(name)
    else:
        assert not hasattr(he_myhook1, name)


def test_decorator_functional(pm):
    class HookSpec(object):
        @hookspec(firstresult=True)
        def he_myhook(self, arg1):
            """ add to arg1 """

    pm.add_hookspecs(HookSpec)

    class Plugin(object):
        @hookimpl()
        def he_myhook(self, arg1):
            return arg1 + 1

    pm.register(Plugin())
    results = pm.hook.he_myhook(arg1=17)
    assert results == 18


def test_load_setuptools_instantiation(monkeypatch, pm):
    pkg_resources = pytest.importorskip("pkg_resources")

    def my_iter(name):
        assert name == "hello"

        class EntryPoint(object):
            name = "myname"
            dist = None

            def load(self):
                class PseudoPlugin(object):
                    x = 42
                return PseudoPlugin()

        return iter([EntryPoint()])

    monkeypatch.setattr(pkg_resources, 'iter_entry_points', my_iter)
    num = pm.load_setuptools_entrypoints("hello")
    assert num == 1
    plugin = pm.get_plugin("myname")
    assert plugin.x == 42
    assert pm.list_plugin_distinfo() == [(plugin, None)]


def test_load_setuptools_not_installed(monkeypatch, pm):
    monkeypatch.setitem(
        sys.modules, 'pkg_resources',
        types.ModuleType("pkg_resources"))

    with pytest.raises(ImportError):
        pm.load_setuptools_entrypoints("qwe")


def test_add_tracefuncs(he_pm):
    l = []

    class api1(object):
        @hookimpl
        def he_method1(self):
            l.append("he_method1-api1")

    class api2(object):
        @hookimpl
        def he_method1(self):
            l.append("he_method1-api2")

    he_pm.register(api1())
    he_pm.register(api2())

    def before(hook_name, hook_impls, kwargs):
        l.append((hook_name, list(hook_impls), kwargs))

    def after(outcome, hook_name, hook_impls, kwargs):
        l.append((outcome, hook_name, list(hook_impls), kwargs))

    undo = he_pm.add_hookcall_monitoring(before, after)

    he_pm.hook.he_method1()
    assert len(l) == 4
    assert l[0][0] == "he_method1"
    assert len(l[0][1]) == 2
    assert isinstance(l[0][2], dict)
    assert l[1] == "he_method1-api2"
    assert l[2] == "he_method1-api1"
    assert len(l[3]) == 4
    assert l[3][1] == l[0][0]

    undo()
    he_pm.hook.he_method1()
    assert len(l) == 4 + 2


def test_hook_tracing(he_pm):
    saveindent = []

    class api1(object):
        @hookimpl
        def he_method1(self):
            saveindent.append(he_pm.trace.root.indent)

    class api2(object):
        @hookimpl
        def he_method1(self):
            saveindent.append(he_pm.trace.root.indent)
            raise ValueError()

    he_pm.register(api1())
    l = []
    he_pm.trace.root.setwriter(l.append)
    undo = he_pm.enable_tracing()
    try:
        indent = he_pm.trace.root.indent
        he_pm.hook.he_method1(arg=1)
        assert indent == he_pm.trace.root.indent
        assert len(l) == 2
        assert 'he_method1' in l[0]
        assert 'finish' in l[1]

        l[:] = []
        he_pm.register(api2())

        with pytest.raises(ValueError):
            he_pm.hook.he_method1(arg=1)
        assert he_pm.trace.root.indent == indent
        assert saveindent[0] > indent
    finally:
        undo()


def test_prefix_hookimpl():
    pm = PluginManager(hookspec.project_name, "hello_")

    class HookSpec(object):
        @hookspec
        def hello_myhook(self, arg1):
            """ add to arg1 """

    pm.add_hookspecs(HookSpec)

    class Plugin(object):
        def hello_myhook(self, arg1):
            return arg1 + 1

    pm.register(Plugin())
    pm.register(Plugin())
    results = pm.hook.hello_myhook(arg1=17)
    assert results == [18, 18]


def test_prefix_hookimpl_dontmatch_module():
    pm = PluginManager(hookspec.project_name, "hello_")

    class BadPlugin(object):
        hello_module = __import__('email')

    pm.register(BadPlugin())
    pm.check_pending()
