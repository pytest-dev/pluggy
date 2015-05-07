
import sys
import types
import pytest

from pluggy import (PluginManager, varnames, PluginValidationError,
                    HookimplMarker, HookspecMarker)

from pluggy import (_MultiCall, _TagTracer, HookImpl)

hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


@pytest.fixture
def pm():
    return PluginManager("example")


@pytest.fixture
def he_pm(pm):
    class Hooks:
        @hookspec
        def he_method1(self, arg):
            return arg + 1

    pm.add_hookspecs(Hooks)
    return pm


class TestPluginManager:
    def test_plugin_double_register(self, pm):
        pm.register(42, name="abc")
        with pytest.raises(ValueError):
            pm.register(42, name="abc")
        with pytest.raises(ValueError):
            pm.register(42, name="def")

    def test_pm(self, pm):
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

    def test_register_dynamic_attr(self, he_pm):
        class A:
            def __getattr__(self, name):
                if name[0] != "_":
                    return 42
                raise AttributeError()

        a = A()
        he_pm.register(a)
        assert not he_pm.get_hookcallers(a)

    def test_pm_name(self, pm):
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

    def test_set_blocked(self, pm):
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

    def test_register_mismatch_method(self, he_pm):
        class hello:
            @hookimpl
            def he_method_notexists(self):
                pass

        he_pm.register(hello())
        with pytest.raises(PluginValidationError):
            he_pm.check_pending()

    def test_register_mismatch_arg(self, he_pm):
        class hello:
            @hookimpl
            def he_method1(self, qlwkje):
                pass

        with pytest.raises(PluginValidationError):
            he_pm.register(hello())

    def test_register(self, pm):
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

    def test_register_unknown_hooks(self, pm):
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

    def test_register_historic(self, pm):
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

    def test_with_result_memorized(self, pm):
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

    def test_register_historic_incompat_hookwrapper(self, pm):
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

    def test_call_extra(self, pm):
        class Hooks:
            @hookspec
            def he_method1(self, arg):
                pass

        pm.add_hookspecs(Hooks)

        def he_method1(arg):
            return arg * 10

        l = pm.hook.he_method1.call_extra([he_method1], dict(arg=1))
        assert l == [10]

    def test_subset_hook_caller(self, pm):
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

    def test_add_hookspecs_nohooks(self, pm):
        with pytest.raises(ValueError):
            pm.add_hookspecs(10)


class TestAddMethodOrdering:
    @pytest.fixture
    def hc(self, pm):
        class Hooks:
            @hookspec
            def he_method1(self, arg):
                pass
        pm.add_hookspecs(Hooks)
        return pm.hook.he_method1

    @pytest.fixture
    def addmeth(self, hc):
        def addmeth(tryfirst=False, trylast=False, hookwrapper=False):
            def wrap(func):
                hookimpl(tryfirst=tryfirst, trylast=trylast,
                         hookwrapper=hookwrapper)(func)
                hc._add_hookimpl(HookImpl(None, "<temp>", func, func.example_impl))
                return func
            return wrap
        return addmeth

    def funcs(self, hookmethods):
        return [hookmethod.function for hookmethod in hookmethods]

    def test_adding_nonwrappers(self, hc, addmeth):
        @addmeth()
        def he_method1():
            pass

        @addmeth()
        def he_method2():
            pass

        @addmeth()
        def he_method3():
            pass
        assert self.funcs(hc._nonwrappers) == [he_method1, he_method2, he_method3]

    def test_adding_nonwrappers_trylast(self, hc, addmeth):
        @addmeth()
        def he_method1_middle():
            pass

        @addmeth(trylast=True)
        def he_method1():
            pass

        @addmeth()
        def he_method1_b():
            pass
        assert self.funcs(hc._nonwrappers) == \
               [he_method1, he_method1_middle, he_method1_b]

    def test_adding_nonwrappers_trylast3(self, hc, addmeth):
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
        assert self.funcs(hc._nonwrappers) == \
               [he_method1_d, he_method1_b, he_method1_a, he_method1_c]

    def test_adding_nonwrappers_trylast2(self, hc, addmeth):
        @addmeth()
        def he_method1_middle():
            pass

        @addmeth()
        def he_method1_b():
            pass

        @addmeth(trylast=True)
        def he_method1():
            pass
        assert self.funcs(hc._nonwrappers) == \
               [he_method1, he_method1_middle, he_method1_b]

    def test_adding_nonwrappers_tryfirst(self, hc, addmeth):
        @addmeth(tryfirst=True)
        def he_method1():
            pass

        @addmeth()
        def he_method1_middle():
            pass

        @addmeth()
        def he_method1_b():
            pass
        assert self.funcs(hc._nonwrappers) == \
               [he_method1_middle, he_method1_b, he_method1]

    def test_adding_wrappers_ordering(self, hc, addmeth):
        @addmeth(hookwrapper=True)
        def he_method1():
            pass

        @addmeth()
        def he_method1_middle():
            pass

        @addmeth(hookwrapper=True)
        def he_method3():
            pass

        assert self.funcs(hc._nonwrappers) == [he_method1_middle]
        assert self.funcs(hc._wrappers) == [he_method1, he_method3]

    def test_adding_wrappers_ordering_tryfirst(self, hc, addmeth):
        @addmeth(hookwrapper=True, tryfirst=True)
        def he_method1():
            pass

        @addmeth(hookwrapper=True)
        def he_method2():
            pass

        assert hc._nonwrappers == []
        assert self.funcs(hc._wrappers) == [he_method2, he_method1]

    def test_hookspec(self, pm):
        class HookSpec:
            @hookspec()
            def he_myhook1(self, arg1):
                pass

            @hookspec(firstresult=True)
            def he_myhook2(self, arg1):
                pass

            @hookspec(firstresult=False)
            def he_myhook3(self, arg1):
                pass

        pm.add_hookspecs(HookSpec)
        assert not pm.hook.he_myhook1.spec_opts["firstresult"]
        assert pm.hook.he_myhook2.spec_opts["firstresult"]
        assert not pm.hook.he_myhook3.spec_opts["firstresult"]

    def test_hookimpl(self):
        for name in ["hookwrapper", "optionalhook", "tryfirst", "trylast"]:
            for val in [True, False]:
                @hookimpl(**{name: val})
                def he_myhook1(self, arg1):
                    pass
                if val:
                    assert he_myhook1.example_impl.get(name)
                else:
                    assert not hasattr(he_myhook1, name)

    def test_decorator_functional(self, pm):
        class HookSpec:
            @hookspec(firstresult=True)
            def he_myhook(self, arg1):
                """ add to arg1 """

        pm.add_hookspecs(HookSpec)

        class Plugin:
            @hookimpl()
            def he_myhook(self, arg1):
                return arg1 + 1

        pm.register(Plugin())
        results = pm.hook.he_myhook(arg1=17)
        assert results == 18

    def test_load_setuptools_instantiation(self, monkeypatch, pm):
        pkg_resources = pytest.importorskip("pkg_resources")

        def my_iter(name):
            assert name == "hello"

            class EntryPoint:
                name = "myname"
                dist = None

                def load(self):
                    class PseudoPlugin:
                        x = 42
                    return PseudoPlugin()

            return iter([EntryPoint()])

        monkeypatch.setattr(pkg_resources, 'iter_entry_points', my_iter)
        num = pm.load_setuptools_entrypoints("hello")
        assert num == 1
        plugin = pm.get_plugin("myname")
        assert plugin.x == 42
        assert pm.list_plugin_distinfo() == [(plugin, None)]

    def test_load_setuptools_not_installed(self, monkeypatch, pm):
        monkeypatch.setitem(sys.modules, 'pkg_resources',
            types.ModuleType("pkg_resources"))

        with pytest.raises(ImportError):
            pm.load_setuptools_entrypoints("qwe")

    def test_add_tracefuncs(self, he_pm):
        l = []

        class api1:
            @hookimpl
            def he_method1(self):
                l.append("he_method1-api1")

        class api2:
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

    def test_hook_tracing(self, he_pm):
        saveindent = []

        class api1:
            @hookimpl
            def he_method1(self):
                saveindent.append(he_pm.trace.root.indent)

        class api2:
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

    def test_prefix_hookimpl(self):
        pm = PluginManager(hookspec.project_name, "hello_")

        class HookSpec:
            @hookspec
            def hello_myhook(self, arg1):
                """ add to arg1 """

        pm.add_hookspecs(HookSpec)

        class Plugin:
            def hello_myhook(self, arg1):
                return arg1 + 1

        pm.register(Plugin())
        pm.register(Plugin())
        results = pm.hook.hello_myhook(arg1=17)
        assert results == [18, 18]


def test_parse_hookimpl_override():
    class MyPluginManager(PluginManager):
        def parse_hookimpl_opts(self, module_or_class, name):
            opts = PluginManager.parse_hookimpl_opts(self, module_or_class, name)
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


def test_varnames():
    def f(x):
        i = 3  # noqa

    class A:
        def f(self, y):
            pass

    class B(object):
        def __call__(self, z):
            pass

    assert varnames(f) == ("x",)
    assert varnames(A().f) == ('y',)
    assert varnames(B()) == ('z',)


def test_varnames_default():
    def f(x, y=3):
        pass

    assert varnames(f) == ("x",)


def test_varnames_class():
    class C:
        def __init__(self, x):
            pass

    class D:
        pass

    assert varnames(C) == ("x",)
    assert varnames(D) == ()


class Test_MultiCall:
    def test_uses_copy_of_methods(self):
        l = [lambda: 42]
        mc = _MultiCall(l, {})
        repr(mc)
        l[:] = []
        res = mc.execute()
        return res == 42

    def MC(self, methods, kwargs, firstresult=False):
        hookfuncs = []
        for method in methods:
            f = HookImpl(None, "<temp>", method, method.example_impl)
            hookfuncs.append(f)
        return _MultiCall(hookfuncs, kwargs, {"firstresult": firstresult})

    def test_call_passing(self):
        class P1:
            @hookimpl
            def m(self, __multicall__, x):
                assert len(__multicall__.results) == 1
                assert not __multicall__.hook_impls
                return 17

        class P2:
            @hookimpl
            def m(self, __multicall__, x):
                assert __multicall__.results == []
                assert __multicall__.hook_impls
                return 23

        p1 = P1()
        p2 = P2()
        multicall = self.MC([p1.m, p2.m], {"x": 23})
        assert "23" in repr(multicall)
        reslist = multicall.execute()
        assert len(reslist) == 2
        # ensure reversed order
        assert reslist == [23, 17]

    def test_keyword_args(self):
        @hookimpl
        def f(x):
            return x + 1

        class A:
            @hookimpl
            def f(self, x, y):
                return x + y

        multicall = self.MC([f, A().f], dict(x=23, y=24))
        assert "'x': 23" in repr(multicall)
        assert "'y': 24" in repr(multicall)
        reslist = multicall.execute()
        assert reslist == [24 + 23, 24]
        assert "2 results" in repr(multicall)

    def test_keyword_args_with_defaultargs(self):
        @hookimpl
        def f(x, z=1):
            return x + z
        reslist = self.MC([f], dict(x=23, y=24)).execute()
        assert reslist == [24]

    def test_tags_call_error(self):
        @hookimpl
        def f(x):
            return x
        multicall = self.MC([f], {})
        pytest.raises(KeyError, multicall.execute)

    def test_call_subexecute(self):
        @hookimpl
        def m(__multicall__):
            subresult = __multicall__.execute()
            return subresult + 1

        @hookimpl
        def n():
            return 1

        call = self.MC([n, m], {}, firstresult=True)
        res = call.execute()
        assert res == 2

    def test_call_none_is_no_result(self):
        @hookimpl
        def m1():
            return 1

        @hookimpl
        def m2():
            return None

        res = self.MC([m1, m2], {}, {"firstresult": True}).execute()
        assert res == 1
        res = self.MC([m1, m2], {}, {}).execute()
        assert res == [1]

    def test_hookwrapper(self):
        l = []

        @hookimpl(hookwrapper=True)
        def m1():
            l.append("m1 init")
            yield None
            l.append("m1 finish")

        @hookimpl
        def m2():
            l.append("m2")
            return 2

        res = self.MC([m2, m1], {}).execute()
        assert res == [2]
        assert l == ["m1 init", "m2", "m1 finish"]
        l[:] = []
        res = self.MC([m2, m1], {}, {"firstresult": True}).execute()
        assert res == 2
        assert l == ["m1 init", "m2", "m1 finish"]

    def test_hookwrapper_order(self):
        l = []

        @hookimpl(hookwrapper=True)
        def m1():
            l.append("m1 init")
            yield 1
            l.append("m1 finish")

        @hookimpl(hookwrapper=True)
        def m2():
            l.append("m2 init")
            yield 2
            l.append("m2 finish")

        res = self.MC([m2, m1], {}).execute()
        assert res == []
        assert l == ["m1 init", "m2 init", "m2 finish", "m1 finish"]

    def test_hookwrapper_not_yield(self):
        @hookimpl(hookwrapper=True)
        def m1():
            pass

        mc = self.MC([m1], {})
        with pytest.raises(TypeError):
            mc.execute()

    def test_hookwrapper_too_many_yield(self):
        @hookimpl(hookwrapper=True)
        def m1():
            yield 1
            yield 2

        mc = self.MC([m1], {})
        with pytest.raises(RuntimeError) as ex:
            mc.execute()
        assert "m1" in str(ex.value)
        assert "test_pluggy.py:" in str(ex.value)

    @pytest.mark.parametrize("exc", [ValueError, SystemExit])
    def test_hookwrapper_exception(self, exc):
        l = []

        @hookimpl(hookwrapper=True)
        def m1():
            l.append("m1 init")
            yield None
            l.append("m1 finish")

        @hookimpl
        def m2():
            raise exc

        with pytest.raises(exc):
            self.MC([m2, m1], {}).execute()
        assert l == ["m1 init", "m1 finish"]


class TestHookRelay:
    def test_hapmypath(self, pm):
        class Api:
            @hookspec
            def hello(self, arg):
                "api hook 1"

        pm.add_hookspecs(Api)
        hook = pm.hook
        assert hasattr(hook, 'hello')
        assert repr(hook.hello).find("hello") != -1

        class Plugin:
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

    def test_argmismatch(self, pm):
        class Api:
            @hookspec
            def hello(self, arg):
                "api hook 1"

        pm.add_hookspecs(Api)

        class Plugin:
            @hookimpl
            def hello(self, argwrong):
                pass

        with pytest.raises(PluginValidationError) as exc:
            pm.register(Plugin())

        assert "argwrong" in str(exc.value)

    def test_only_kwargs(self, pm):
        class Api:
            @hookspec
            def hello(self, arg):
                "api hook 1"

        pm.add_hookspecs(Api)
        pytest.raises(TypeError, lambda: pm.hook.hello(3))

    def test_firstresult_definition(self, pm):
        class Api:
            @hookspec(firstresult=True)
            def hello(self, arg):
                "api hook 1"

        pm.add_hookspecs(Api)

        class Plugin:
            @hookimpl
            def hello(self, arg):
                return arg + 1

        pm.register(Plugin())
        res = pm.hook.hello(arg=3)
        assert res == 4


class TestTracer:
    def test_simple(self):
        rootlogger = _TagTracer()
        log = rootlogger.get("pytest")
        log("hello")
        l = []
        rootlogger.setwriter(l.append)
        log("world")
        assert len(l) == 1
        assert l[0] == "world [pytest]\n"
        sublog = log.get("collection")
        sublog("hello")
        assert l[1] == "hello [pytest:collection]\n"

    def test_indent(self):
        rootlogger = _TagTracer()
        log = rootlogger.get("1")
        l = []
        log.root.setwriter(lambda arg: l.append(arg))
        log("hello")
        log.root.indent += 1
        log("line1")
        log("line2")
        log.root.indent += 1
        log("line3")
        log("line4")
        log.root.indent -= 1
        log("line5")
        log.root.indent -= 1
        log("last")
        assert len(l) == 7
        names = [x[:x.rfind(' [')] for x in l]
        assert names == ['hello', '  line1', '  line2',
                     '    line3', '    line4', '  line5', 'last']

    def test_readable_output_dictargs(self):
        rootlogger = _TagTracer()

        out = rootlogger.format_message(['test'], [1])
        assert out == ['1 [test]\n']

        out2 = rootlogger.format_message(['test'], ['test', {'a': 1}])
        assert out2 == [
            'test [test]\n',
            '    a: 1\n'
        ]

    def test_setprocessor(self):
        rootlogger = _TagTracer()
        log = rootlogger.get("1")
        log2 = log.get("2")
        assert log2.tags == tuple("12")
        l = []
        rootlogger.setprocessor(tuple("12"), lambda *args: l.append(args))
        log("not seen")
        log2("seen")
        assert len(l) == 1
        tags, args = l[0]
        assert "1" in tags
        assert "2" in tags
        assert args == ("seen",)
        l2 = []
        rootlogger.setprocessor("1:2", lambda *args: l2.append(args))
        log2("seen")
        tags, args = l2[0]
        assert args == ("seen",)

    def test_setmyprocessor(self):
        rootlogger = _TagTracer()
        log = rootlogger.get("1")
        log2 = log.get("2")
        l = []
        log2.setmyprocessor(lambda *args: l.append(args))
        log("not seen")
        assert not l
        log2(42)
        assert len(l) == 1
        tags, args = l[0]
        assert "1" in tags
        assert "2" in tags
        assert args == (42,)
