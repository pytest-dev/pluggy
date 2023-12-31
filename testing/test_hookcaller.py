from typing import Callable
from typing import List
from typing import Sequence
from typing import TypeVar

import pytest

from pluggy import HookimplMarker
from pluggy import HookspecMarker
from pluggy import PluginManager
from pluggy import PluginValidationError
from pluggy._hooks import HookCaller
from pluggy._hooks import HookImpl
from pluggy._hooks import HookimplOpts
from pluggy._tracing import saferepr

hookspec = HookspecMarker("example")
hookimpl = HookimplMarker("example")


@pytest.fixture
def hc(pm: PluginManager) -> HookCaller:
    class Hooks:
        @hookspec
        def he_method1(self, arg: object) -> None:
            pass

    pm.add_hookspecs(Hooks)
    return pm.hook.he_method1


FuncT = TypeVar("FuncT", bound=Callable[..., object])


class AddMeth:
    def __init__(self, hc: HookCaller) -> None:
        self.hc = hc

    def __call__(
        self,
        tryfirst: bool = False,
        trylast: bool = False,
        hookwrapper: bool = False,
        wrapper: bool = False,
    ) -> Callable[[FuncT], FuncT]:
        def wrap(func: FuncT) -> FuncT:
            hookimpl(
                tryfirst=tryfirst,
                trylast=trylast,
                hookwrapper=hookwrapper,
                wrapper=wrapper,
            )(func)
            self.hc._add_hookimpl(
                HookImpl(None, "<temp>", func, func.example_impl),  # type: ignore[attr-defined]
            )
            return func

        return wrap


@pytest.fixture
def addmeth(hc: HookCaller) -> AddMeth:
    return AddMeth(hc)


def funcs(hookmethods: Sequence[HookImpl]) -> List[Callable[..., object]]:
    return [hookmethod.function for hookmethod in hookmethods]


def test_adding_nonwrappers(hc: HookCaller, addmeth: AddMeth) -> None:
    @addmeth()
    def he_method1() -> None:
        pass

    @addmeth()
    def he_method2() -> None:
        pass

    @addmeth()
    def he_method3() -> None:
        pass

    assert funcs(hc.get_hookimpls()) == [he_method1, he_method2, he_method3]


def test_adding_nonwrappers_trylast(hc: HookCaller, addmeth: AddMeth) -> None:
    @addmeth()
    def he_method1_middle() -> None:
        pass

    @addmeth(trylast=True)
    def he_method1() -> None:
        pass

    @addmeth()
    def he_method1_b() -> None:
        pass

    assert funcs(hc.get_hookimpls()) == [he_method1, he_method1_middle, he_method1_b]


def test_adding_nonwrappers_trylast3(hc: HookCaller, addmeth: AddMeth) -> None:
    @addmeth()
    def he_method1_a() -> None:
        pass

    @addmeth(trylast=True)
    def he_method1_b() -> None:
        pass

    @addmeth()
    def he_method1_c() -> None:
        pass

    @addmeth(trylast=True)
    def he_method1_d() -> None:
        pass

    assert funcs(hc.get_hookimpls()) == [
        he_method1_d,
        he_method1_b,
        he_method1_a,
        he_method1_c,
    ]


def test_adding_nonwrappers_trylast2(hc: HookCaller, addmeth: AddMeth) -> None:
    @addmeth()
    def he_method1_middle() -> None:
        pass

    @addmeth()
    def he_method1_b() -> None:
        pass

    @addmeth(trylast=True)
    def he_method1() -> None:
        pass

    assert funcs(hc.get_hookimpls()) == [he_method1, he_method1_middle, he_method1_b]


def test_adding_nonwrappers_tryfirst(hc: HookCaller, addmeth: AddMeth) -> None:
    @addmeth(tryfirst=True)
    def he_method1() -> None:
        pass

    @addmeth()
    def he_method1_middle() -> None:
        pass

    @addmeth()
    def he_method1_b() -> None:
        pass

    assert funcs(hc.get_hookimpls()) == [he_method1_middle, he_method1_b, he_method1]


def test_adding_wrappers_ordering(hc: HookCaller, addmeth: AddMeth) -> None:
    @addmeth(hookwrapper=True)
    def he_method1():
        yield

    @addmeth(wrapper=True)
    def he_method1_fun():
        yield

    @addmeth()
    def he_method1_middle():
        return

    @addmeth(hookwrapper=True)
    def he_method3_fun():
        yield

    @addmeth(hookwrapper=True)
    def he_method3():
        yield

    assert funcs(hc.get_hookimpls()) == [
        he_method1_middle,
        he_method1,
        he_method1_fun,
        he_method3_fun,
        he_method3,
    ]


def test_adding_wrappers_ordering_tryfirst(hc: HookCaller, addmeth: AddMeth) -> None:
    @addmeth(hookwrapper=True, tryfirst=True)
    def he_method1():
        yield

    @addmeth(hookwrapper=True)
    def he_method2():
        yield

    @addmeth(wrapper=True, tryfirst=True)
    def he_method3():
        yield

    assert funcs(hc.get_hookimpls()) == [he_method2, he_method1, he_method3]


def test_adding_wrappers_complex(hc: HookCaller, addmeth: AddMeth) -> None:
    assert funcs(hc.get_hookimpls()) == []

    @addmeth(hookwrapper=True, trylast=True)
    def m1():
        yield

    assert funcs(hc.get_hookimpls()) == [m1]

    @addmeth()
    def m2() -> None:
        ...

    assert funcs(hc.get_hookimpls()) == [m2, m1]

    @addmeth(trylast=True)
    def m3() -> None:
        ...

    assert funcs(hc.get_hookimpls()) == [m3, m2, m1]

    @addmeth(hookwrapper=True)
    def m4() -> None:
        ...

    assert funcs(hc.get_hookimpls()) == [m3, m2, m1, m4]

    @addmeth(wrapper=True, tryfirst=True)
    def m5():
        yield

    assert funcs(hc.get_hookimpls()) == [m3, m2, m1, m4, m5]

    @addmeth(tryfirst=True)
    def m6() -> None:
        ...

    assert funcs(hc.get_hookimpls()) == [m3, m2, m6, m1, m4, m5]

    @addmeth()
    def m7() -> None:
        ...

    assert funcs(hc.get_hookimpls()) == [m3, m2, m7, m6, m1, m4, m5]

    @addmeth(wrapper=True)
    def m8():
        yield

    assert funcs(hc.get_hookimpls()) == [m3, m2, m7, m6, m1, m4, m8, m5]

    @addmeth(trylast=True)
    def m9() -> None:
        ...

    assert funcs(hc.get_hookimpls()) == [m9, m3, m2, m7, m6, m1, m4, m8, m5]

    @addmeth(tryfirst=True)
    def m10() -> None:
        ...

    assert funcs(hc.get_hookimpls()) == [m9, m3, m2, m7, m6, m10, m1, m4, m8, m5]

    @addmeth(hookwrapper=True, trylast=True)
    def m11() -> None:
        ...

    assert funcs(hc.get_hookimpls()) == [m9, m3, m2, m7, m6, m10, m11, m1, m4, m8, m5]

    @addmeth(wrapper=True)
    def m12():
        yield

    assert funcs(hc.get_hookimpls()) == [
        m9,
        m3,
        m2,
        m7,
        m6,
        m10,
        m11,
        m1,
        m4,
        m8,
        m12,
        m5,
    ]

    @addmeth()
    def m13() -> None:
        ...

    assert funcs(hc.get_hookimpls()) == [
        m9,
        m3,
        m2,
        m7,
        m13,
        m6,
        m10,
        m11,
        m1,
        m4,
        m8,
        m12,
        m5,
    ]


def test_hookspec(pm: PluginManager) -> None:
    class HookSpec:
        @hookspec()
        def he_myhook1(arg1) -> None:
            pass

        @hookspec(firstresult=True)
        def he_myhook2(arg1) -> None:
            pass

        @hookspec(firstresult=False)
        def he_myhook3(arg1) -> None:
            pass

    pm.add_hookspecs(HookSpec)
    assert pm.hook.he_myhook1.spec is not None
    assert not pm.hook.he_myhook1.spec.opts["firstresult"]
    assert pm.hook.he_myhook2.spec is not None
    assert pm.hook.he_myhook2.spec.opts["firstresult"]
    assert pm.hook.he_myhook3.spec is not None
    assert not pm.hook.he_myhook3.spec.opts["firstresult"]


@pytest.mark.parametrize("name", ["hookwrapper", "optionalhook", "tryfirst", "trylast"])
@pytest.mark.parametrize("val", [True, False])
def test_hookimpl(name: str, val: bool) -> None:
    @hookimpl(**{name: val})  # type: ignore[misc,call-overload]
    def he_myhook1(arg1) -> None:
        pass

    if val:
        assert he_myhook1.example_impl.get(name)
    else:
        assert not hasattr(he_myhook1, name)


def test_hookrelay_registry(pm: PluginManager) -> None:
    """Verify hook caller instances are registered by name onto the relay
    and can be likewise unregistered."""

    class Api:
        @hookspec
        def hello(self, arg: object) -> None:
            "api hook 1"

    pm.add_hookspecs(Api)
    hook = pm.hook
    assert hasattr(hook, "hello")
    assert repr(hook.hello).find("hello") != -1

    class Plugin:
        @hookimpl
        def hello(self, arg):
            return arg + 1

    plugin = Plugin()
    pm.register(plugin)
    out = hook.hello(arg=3)
    assert out == [4]
    assert not hasattr(hook, "world")
    pm.unregister(plugin)
    assert hook.hello(arg=3) == []


def test_hookrelay_registration_by_specname(pm: PluginManager) -> None:
    """Verify hook caller instances may also be registered by specifying a
    specname option to the hookimpl"""

    class Api:
        @hookspec
        def hello(self, arg: object) -> None:
            "api hook 1"

    pm.add_hookspecs(Api)
    hook = pm.hook
    assert hasattr(hook, "hello")
    assert len(pm.hook.hello.get_hookimpls()) == 0

    class Plugin:
        @hookimpl(specname="hello")
        def foo(self, arg: int) -> int:
            return arg + 1

    plugin = Plugin()
    pm.register(plugin)
    out = hook.hello(arg=3)
    assert out == [4]


def test_hookrelay_registration_by_specname_raises(pm: PluginManager) -> None:
    """Verify using specname still raises the types of errors during registration as it
    would have without using specname."""

    class Api:
        @hookspec
        def hello(self, arg: object) -> None:
            "api hook 1"

    pm.add_hookspecs(Api)

    """make sure a bad signature still raises an error when using specname"""

    class Plugin:
        @hookimpl(specname="hello")
        def foo(self, arg: int, too, many, args) -> int:
            return arg + 1

    with pytest.raises(PluginValidationError):
        pm.register(Plugin())

    """make sure check_pending still fails if specname doesn't have a
    corresponding spec.  EVEN if the function name matches one."""

    class Plugin2:
        @hookimpl(specname="bar")
        def hello(self, arg: int) -> int:
            return arg + 1

    pm.register(Plugin2())
    with pytest.raises(PluginValidationError):
        pm.check_pending()


def test_hook_conflict(pm: PluginManager) -> None:
    class Api1:
        @hookspec
        def conflict(self) -> None:
            """Api1 hook"""

    class Api2:
        @hookspec
        def conflict(self) -> None:
            """Api2 hook"""

    pm.add_hookspecs(Api1)
    with pytest.raises(ValueError) as exc:
        pm.add_hookspecs(Api2)
    assert str(exc.value) == (
        "Hook 'conflict' is already registered within namespace "
        "<class 'test_hookcaller.test_hook_conflict.<locals>.Api1'>"
    )


def test_hook_impl_initialization() -> None:
    # Mock data
    plugin = "example_plugin"
    plugin_name = "ExamplePlugin"

    def example_function(x):
        return x

    hook_impl_opts: HookimplOpts = {
        "wrapper": False,
        "hookwrapper": False,
        "optionalhook": False,
        "tryfirst": False,
        "trylast": False,
        "specname": "",
    }

    # Initialize HookImpl
    hook_impl = HookImpl(plugin, plugin_name, example_function, hook_impl_opts)

    # Verify attributes are set correctly
    assert hook_impl.function == example_function
    assert hook_impl.argnames == ("x",)
    assert hook_impl.kwargnames == ()
    assert hook_impl.plugin == plugin
    assert hook_impl.opts == hook_impl_opts
    assert hook_impl.plugin_name == plugin_name
    assert not hook_impl.wrapper
    assert not hook_impl.hookwrapper
    assert not hook_impl.optionalhook
    assert not hook_impl.tryfirst
    assert not hook_impl.trylast


def test_hook_impl_representation() -> None:
    # Mock data
    plugin = "example_plugin"
    plugin_name = "ExamplePlugin"

    def example_function(x):
        return x

    hook_impl_opts: HookimplOpts = {
        "wrapper": False,
        "hookwrapper": False,
        "optionalhook": False,
        "tryfirst": False,
        "trylast": False,
        "specname": "",
    }

    # Initialize HookImpl
    hook_impl = HookImpl(plugin, plugin_name, example_function, hook_impl_opts)

    # Verify __repr__ method
    expected_repr = (
        f"<HookImpl plugin_name={saferepr(plugin_name)}, " f"plugin={saferepr(plugin)}>"
    )
    assert repr(hook_impl) == expected_repr
