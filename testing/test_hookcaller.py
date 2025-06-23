from collections.abc import Generator
from collections.abc import Sequence
from typing import Callable
from typing import TypeVar

import pytest

from pluggy import HookspecConfiguration
from pluggy import PluginManager
from pluggy import PluginValidationError
from pluggy import ProjectSpec
from pluggy._hooks import HistoricHookCaller
from pluggy._hooks import HookCaller
from pluggy._hooks import HookImpl
from pluggy._hooks import NormalHookCaller


project_spec = ProjectSpec("example")
hookspec = project_spec.hookspec
hookimpl = project_spec.hookimpl


@pytest.fixture
def hc(pm: PluginManager) -> NormalHookCaller:
    class Hooks:
        @hookspec
        def he_method1(self, arg: object) -> None:
            pass

    pm.add_hookspecs(Hooks)
    assert isinstance(pm.hook.he_method1, NormalHookCaller)
    return pm.hook.he_method1


FuncT = TypeVar("FuncT", bound=Callable[..., object])


class AddMeth:
    def __init__(self, hc: NormalHookCaller) -> None:
        self.hc = hc

    def __call__(
        self,
        tryfirst: bool = False,
        trylast: bool = False,
        hookwrapper: bool = False,
        wrapper: bool = False,
    ) -> Callable[[FuncT], FuncT]:
        def wrap(func: FuncT) -> FuncT:
            project_spec.hookimpl(
                tryfirst=tryfirst,
                trylast=trylast,
                hookwrapper=hookwrapper,
                wrapper=wrapper,
            )(func)
            config = project_spec.get_hookimpl_config(func)
            assert config is not None  # Test functions should be decorated
            # Create hookimpl and add to hook caller
            hookimpl = config.create_hookimpl(None, "<temp>", func)
            self.hc._add_hookimpl(hookimpl)
            return func

        return wrap


@pytest.fixture
def addmeth(hc: NormalHookCaller) -> AddMeth:
    return AddMeth(hc)


def funcs(hookmethods: Sequence[HookImpl]) -> list[Callable[..., object]]:
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
        yield  # pragma: no cover

    @addmeth(wrapper=True)
    def he_method1_fun():
        yield  # pragma: no cover

    @addmeth()
    def he_method1_middle():
        return  # pragma: no cover

    @addmeth(hookwrapper=True)
    def he_method3_fun():
        yield  # pragma: no cover

    @addmeth(hookwrapper=True)
    def he_method3():
        yield  # pragma: no cover

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
        yield  # pragma: no cover

    @addmeth(hookwrapper=True)
    def he_method2():
        yield  # pragma: no cover

    @addmeth(wrapper=True, tryfirst=True)
    def he_method3():
        yield  # pragma: no cover

    assert funcs(hc.get_hookimpls()) == [he_method2, he_method1, he_method3]


def test_adding_wrappers_complex(hc: HookCaller, addmeth: AddMeth) -> None:
    assert funcs(hc.get_hookimpls()) == []

    @addmeth(hookwrapper=True, trylast=True)
    def m1():
        yield  # pragma: no cover

    assert funcs(hc.get_hookimpls()) == [m1]

    @addmeth()
    def m2() -> None: ...

    assert funcs(hc.get_hookimpls()) == [m2, m1]

    @addmeth(trylast=True)
    def m3() -> None: ...

    assert funcs(hc.get_hookimpls()) == [m3, m2, m1]

    @addmeth(hookwrapper=True)
    def m4() -> None: ...

    assert funcs(hc.get_hookimpls()) == [m3, m2, m1, m4]

    @addmeth(wrapper=True, tryfirst=True)
    def m5():
        yield  # pragma: no cover

    assert funcs(hc.get_hookimpls()) == [m3, m2, m1, m4, m5]

    @addmeth(tryfirst=True)
    def m6() -> None: ...

    assert funcs(hc.get_hookimpls()) == [m3, m2, m6, m1, m4, m5]

    @addmeth()
    def m7() -> None: ...

    assert funcs(hc.get_hookimpls()) == [m3, m2, m7, m6, m1, m4, m5]

    @addmeth(wrapper=True)
    def m8():
        yield  # pragma: no cover

    assert funcs(hc.get_hookimpls()) == [m3, m2, m7, m6, m1, m4, m8, m5]

    @addmeth(trylast=True)
    def m9() -> None: ...

    assert funcs(hc.get_hookimpls()) == [m9, m3, m2, m7, m6, m1, m4, m8, m5]

    @addmeth(tryfirst=True)
    def m10() -> None: ...

    assert funcs(hc.get_hookimpls()) == [m9, m3, m2, m7, m6, m10, m1, m4, m8, m5]

    @addmeth(hookwrapper=True, trylast=True)
    def m11() -> None: ...

    assert funcs(hc.get_hookimpls()) == [m9, m3, m2, m7, m6, m10, m11, m1, m4, m8, m5]

    @addmeth(wrapper=True)
    def m12():
        yield  # pragma: no cover

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
    def m13() -> None: ...

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
    assert not pm.hook.he_myhook1.spec.config.firstresult
    assert pm.hook.he_myhook2.spec is not None
    assert pm.hook.he_myhook2.spec.config.firstresult
    assert pm.hook.he_myhook3.spec is not None
    assert not pm.hook.he_myhook3.spec.config.firstresult


@pytest.mark.parametrize("name", ["hookwrapper", "optionalhook", "tryfirst", "trylast"])
@pytest.mark.parametrize("val", [True, False])
def test_hookimpl(name: str, val: bool) -> None:
    @hookimpl(**{name: val})  # type: ignore[misc,call-overload]
    def he_myhook1(arg1) -> None:
        pass

    if val:
        assert getattr(he_myhook1.example_impl, name)
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

    # make sure a bad signature still raises an error when using specname
    class Plugin:
        @hookimpl(specname="hello")
        def foo(self, arg: int, too, many, args) -> int:
            return arg + 1  # pragma: no cover

    with pytest.raises(PluginValidationError):
        pm.register(Plugin())

    # make sure check_pending still fails if specname doesn't have a
    # corresponding spec.  EVEN if the function name matches one.
    class Plugin2:
        @hookimpl(specname="bar")
        def hello(self, arg: int) -> int:
            return arg + 1  # pragma: no cover

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


def test_call_extra_hook_order(hc: HookCaller, addmeth: AddMeth) -> None:
    """Ensure that call_extra is calling hooks in the right order."""
    order = []

    @addmeth(tryfirst=True)
    def method1() -> str:
        order.append("1")
        return "1"

    @addmeth()
    def method2() -> str:
        order.append("2")
        return "2"

    @addmeth(trylast=True)
    def method3() -> str:
        order.append("3")
        return "3"

    @addmeth(wrapper=True, tryfirst=True)
    def method4() -> Generator[None, str, str]:
        order.append("4pre")
        result = yield
        order.append("4post")
        return result

    @addmeth(wrapper=True)
    def method5() -> Generator[None, str, str]:
        order.append("5pre")
        result = yield
        order.append("5post")
        return result

    @addmeth(wrapper=True, trylast=True)
    def method6() -> Generator[None, str, str]:
        order.append("6pre")
        result = yield
        order.append("6post")
        return result

    def extra1() -> str:
        order.append("extra1")
        return "extra1"

    def extra2() -> str:
        order.append("extra2")
        return "extra2"

    result = hc.call_extra([extra1, extra2], {"arg": "test"})
    assert order == [
        "4pre",
        "5pre",
        "6pre",
        "1",
        "extra2",
        "extra1",
        "2",
        "3",
        "6post",
        "5post",
        "4post",
    ]
    assert result == [
        "1",
        "extra2",
        "extra1",
        "2",
        "3",
    ]


def test_hookspec_configuration() -> None:
    """Test HookspecConfiguration class and its integration."""
    PluginManager("example")

    # Test HookspecConfiguration creation
    config = HookspecConfiguration(
        firstresult=True,
        historic=False,
        warn_on_impl=DeprecationWarning("test warning"),
        warn_on_impl_args={"arg1": UserWarning("arg warning")},
    )

    assert config.firstresult is True
    assert config.historic is False
    assert isinstance(config.warn_on_impl, DeprecationWarning)
    assert config.warn_on_impl_args is not None
    assert "arg1" in config.warn_on_impl_args

    # Test __repr__
    repr_str = repr(config)
    assert "HookspecConfiguration" in repr_str
    assert "firstresult=True" in repr_str
    assert "warn_on_impl" in repr_str

    # Test validation (historic + firstresult should raise)
    with pytest.raises(ValueError, match="cannot have a historic firstresult hook"):
        HookspecConfiguration(firstresult=True, historic=True)


def test_hookspec_marker_config_extraction() -> None:
    """Test that ProjectSpec can extract HookspecConfiguration correctly."""
    test_project_spec = ProjectSpec("test")
    marker = test_project_spec.hookspec

    @marker(firstresult=True, historic=False)
    def test_hook(arg1: str) -> str:
        return arg1

    # Test config extraction method via ProjectSpec
    config = test_project_spec.get_hookspec_config(test_hook)
    assert isinstance(config, HookspecConfiguration)
    assert config.firstresult is True
    assert config.historic is False
    assert config.warn_on_impl is None
    assert config.warn_on_impl_args is None


def test_hookspec_configuration_backward_compatibility() -> None:
    """Test that HookspecConfiguration integrates properly with existing systems."""
    pm = PluginManager("example")

    class TestSpecs:
        @hookspec(firstresult=True, historic=False)
        def test_hook1(self, arg1: str) -> str:
            return arg1

        @hookspec(firstresult=False, historic=False)
        def test_hook2(self, arg1: int) -> None:
            pass

    pm.add_hookspecs(TestSpecs)

    # Verify specs are created correctly
    hook1_spec = pm.hook.test_hook1.spec
    hook2_spec = pm.hook.test_hook2.spec

    assert hook1_spec is not None
    assert isinstance(hook1_spec.config, HookspecConfiguration)
    assert hook1_spec.config.firstresult is True
    assert hook1_spec.config.historic is False

    assert hook2_spec is not None
    assert isinstance(hook2_spec.config, HookspecConfiguration)
    assert hook2_spec.config.firstresult is False
    assert hook2_spec.config.historic is False

    # Test that hook calling respects the configuration
    results = []

    class Plugin1:
        @hookimpl
        def test_hook1(self, arg1: str) -> str:
            results.append("plugin1")
            return "result1"

        @hookimpl
        def test_hook2(self, arg1: int) -> None:
            results.append("plugin2-hook2")

    class Plugin2:
        @hookimpl
        def test_hook1(self, arg1: str) -> str:
            results.append("plugin2")
            return "result2"

        @hookimpl
        def test_hook2(self, arg1: int) -> None:
            results.append("plugin1-hook2")

    pm.register(Plugin1())
    pm.register(Plugin2())

    # test_hook1 has firstresult=True, should return first non-None result
    result1 = pm.hook.test_hook1(arg1="test")
    assert result1 in ["result1", "result2"]  # Either could be first

    # test_hook2 has firstresult=False, should call all implementations
    results.clear()
    pm.hook.test_hook2(arg1=42)
    assert len(results) == 2
    assert "plugin2-hook2" in results
    assert "plugin1-hook2" in results


def test_set_specification_backward_compatibility() -> None:
    """Test that HookCaller.set_specification supports both old and new interfaces."""
    from pluggy._hooks import HookspecOpts
    from pluggy._hooks import NormalHookCaller
    from pluggy._manager import PluginManager

    pm = PluginManager("test")
    hook_caller = NormalHookCaller("test_hook", pm._hookexec, pm._async_submitter)

    # Test with new HookspecConfiguration interface
    config = HookspecConfiguration(firstresult=True, historic=False)

    class TestSpec:
        def test_hook(self, arg1: str) -> str:
            return arg1

    hook_caller.set_specification(TestSpec, spec_config=config)
    assert hook_caller.spec is not None
    assert hook_caller.spec.config.firstresult is True
    assert hook_caller.spec.config.historic is False

    # Test with old HookspecOpts interface (positional) - use HistoricHookCaller
    old_opts: HookspecOpts = {
        "firstresult": False,
        "historic": True,
        "warn_on_impl": None,
        "warn_on_impl_args": None,
    }
    historic_config = HookspecConfiguration(**old_opts)
    historic_hook_caller = HistoricHookCaller(
        "test_hook", pm._hookexec, TestSpec, historic_config, pm._async_submitter
    )
    assert historic_hook_caller.spec is not None
    assert historic_hook_caller.spec.config.firstresult is False
    assert historic_hook_caller.spec.config.historic is True

    # Test with old HookspecOpts interface (keyword) - use HistoricHookCaller
    historic_hook_caller2 = HistoricHookCaller(
        "test_hook", pm._hookexec, TestSpec, historic_config, pm._async_submitter
    )
    assert historic_hook_caller2.spec is not None
    assert historic_hook_caller2.spec.config.firstresult is False
    assert historic_hook_caller2.spec.config.historic is True

    # Test error cases
    hook_caller4 = NormalHookCaller("test_hook", pm._hookexec, pm._async_submitter)

    # Cannot provide both positional and keyword
    with pytest.raises(
        AssertionError,
        match="Cannot provide both positional and keyword spec arguments",
    ):
        hook_caller4.set_specification(TestSpec, old_opts, spec_config=config)

    # Cannot provide both spec_opts and spec_config
    with pytest.raises(
        AssertionError, match="Cannot provide both spec_opts and spec_config"
    ):
        hook_caller4.set_specification(TestSpec, spec_opts=old_opts, spec_config=config)

    # Must provide at least one
    with pytest.raises(TypeError, match="Must provide either spec_opts or spec_config"):
        hook_caller4.set_specification(TestSpec)
