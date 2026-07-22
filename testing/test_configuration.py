"""
Tests for configuration classes.
"""

from __future__ import annotations

import pytest

from pluggy import HookimplConfiguration
from pluggy import HookimplMarker
from pluggy import HookspecConfiguration
from pluggy import HookspecMarker
from pluggy import PluginManager
from pluggy._config import hookimpl_config_from_mapping
from pluggy._config import hookspec_config_from_mapping


class TestHookspecConfiguration:
    def test_basic_creation(self) -> None:
        config = HookspecConfiguration()
        assert config.firstresult is False
        assert config.historic is False
        assert config.warn_on_impl is None
        assert config.warn_on_impl_args is None

    def test_firstresult(self) -> None:
        config = HookspecConfiguration(firstresult=True)
        assert config.firstresult is True
        assert config.historic is False

    def test_historic(self) -> None:
        config = HookspecConfiguration(historic=True)
        assert config.firstresult is False
        assert config.historic is True

    def test_historic_firstresult_validation(self) -> None:
        with pytest.raises(ValueError, match="cannot have a historic firstresult"):
            HookspecConfiguration(historic=True, firstresult=True)

    def test_warn_on_impl(self) -> None:
        warning = UserWarning("test warning")
        config = HookspecConfiguration(warn_on_impl=warning)
        assert config.warn_on_impl is warning

    def test_warn_on_impl_args(self) -> None:
        warnings_dict = {"arg1": UserWarning("arg1 warning")}
        config = HookspecConfiguration(warn_on_impl_args=warnings_dict)
        assert config.warn_on_impl_args is warnings_dict


class TestHookimplConfiguration:
    def test_basic_creation(self) -> None:
        config = HookimplConfiguration()
        assert config.wrapper is False
        assert config.hookwrapper is False
        assert config.optionalhook is False
        assert config.tryfirst is False
        assert config.trylast is False
        assert config.specname is None

    def test_wrapper(self) -> None:
        config = HookimplConfiguration(wrapper=True)
        assert config.wrapper is True
        assert config.hookwrapper is False

    def test_hookwrapper(self) -> None:
        config = HookimplConfiguration(hookwrapper=True)
        assert config.wrapper is False
        assert config.hookwrapper is True

    def test_both_wrappers_allowed(self) -> None:
        """Both wrapper types are allowed at config level; validation is later."""
        config = HookimplConfiguration(wrapper=True, hookwrapper=True)
        assert config.wrapper is True
        assert config.hookwrapper is True

    def test_tryfirst(self) -> None:
        config = HookimplConfiguration(tryfirst=True)
        assert config.tryfirst is True
        assert config.trylast is False

    def test_trylast(self) -> None:
        config = HookimplConfiguration(trylast=True)
        assert config.tryfirst is False
        assert config.trylast is True

    def test_optionalhook(self) -> None:
        config = HookimplConfiguration(optionalhook=True)
        assert config.optionalhook is True

    def test_specname(self) -> None:
        config = HookimplConfiguration(specname="custom_name")
        assert config.specname == "custom_name"


class TestMappingShim:
    def test_hookspec_config_from_mapping(self) -> None:
        warning = UserWarning("w")
        config = hookspec_config_from_mapping(
            {
                "firstresult": True,
                "warn_on_impl": warning,
            }
        )
        assert config.firstresult is True
        assert config.historic is False
        assert config.warn_on_impl is warning

    def test_hookimpl_config_from_mapping(self) -> None:
        config = hookimpl_config_from_mapping(
            {
                "tryfirst": True,
                "specname": "other",
            }
        )
        assert config.tryfirst is True
        assert config.specname == "other"
        assert config.wrapper is False

    def test_read_hookimpl_accepts_legacy_dict_attribute(self) -> None:
        pm = PluginManager("test")

        def method() -> str:
            return "ok"

        setattr(method, "test_impl", {"tryfirst": True})

        class Plugin:
            pass

        plugin = Plugin()
        plugin.method = method  # type: ignore[attr-defined]
        config = pm._read_hookimpl_configuration(plugin, "method")
        assert isinstance(config, HookimplConfiguration)
        assert config.tryfirst is True

    def test_parse_hookimpl_opts_returns_legacy_dict(self) -> None:
        hookimpl = HookimplMarker("test")

        @hookimpl(tryfirst=True)
        def method() -> str:
            return "ok"

        class Plugin:
            pass

        plugin = Plugin()
        plugin.method = method  # type: ignore[attr-defined]
        opts = PluginManager("test").parse_hookimpl_opts(plugin, "method")
        assert opts == {
            "wrapper": False,
            "hookwrapper": False,
            "optionalhook": False,
            "tryfirst": True,
            "trylast": False,
            "specname": None,
        }

    def test_read_hookspec_accepts_legacy_dict_attribute(self) -> None:
        pm = PluginManager("test")

        class Spec:
            def myhook(self) -> None:
                pass

        setattr(Spec.myhook, "test_spec", {"firstresult": True})
        config = pm._read_hookspec_configuration(Spec, "myhook")
        assert isinstance(config, HookspecConfiguration)
        assert config.firstresult is True

    def test_discover_skips_parse_hookimpl_opts_unless_overridden(self) -> None:
        calls: list[str] = []

        class TrackingPluginManager(PluginManager):
            def parse_hookimpl_opts(self, plugin: object, name: str):
                calls.append(name)
                return super().parse_hookimpl_opts(plugin, name)

        class Spec:
            @HookspecMarker("test")
            def marked(self) -> None:
                pass

            def unmarked(self) -> None:
                pass

        class Plugin:
            @HookimplMarker("test")
            def marked(self) -> str:
                return "marked"

            def unmarked(self) -> str:
                return "unmarked"

        pm = TrackingPluginManager("test")
        pm.add_hookspecs(Spec)
        pm.register(Plugin())
        # Marked impl is discovered privately; unmarked has no config and the
        # override returns None, so parse_hookimpl_opts is only tried for names
        # without a modern configuration attribute.
        assert "marked" not in calls
        assert "unmarked" in calls


def test_markers_attach_configuration_objects() -> None:
    hookspec = HookspecMarker("test")
    hookimpl = HookimplMarker("test")

    @hookspec(firstresult=True)
    def myspec(arg: object) -> None:
        pass

    @hookimpl(tryfirst=True)
    def myimpl(arg: object) -> str:
        return "x"

    spec_config = getattr(myspec, "test_spec")
    impl_config = getattr(myimpl, "test_impl")
    assert isinstance(spec_config, HookspecConfiguration)
    assert spec_config.firstresult is True
    assert isinstance(impl_config, HookimplConfiguration)
    assert impl_config.tryfirst is True


def test_config_integration_with_hooks() -> None:
    pm = PluginManager("test")
    hookspec = HookspecMarker("test")
    hookimpl = HookimplMarker("test")

    class MySpec:
        @hookspec(firstresult=True)
        def myhook(self, arg: object) -> None:
            pass

    class Plugin1:
        @hookimpl(trylast=True)
        def myhook(self, arg: object) -> str:
            return f"plugin1: {arg}"

    class Plugin2:
        @hookimpl(tryfirst=True)
        def myhook(self, arg: object) -> str:
            return f"plugin2: {arg}"

    pm.add_hookspecs(MySpec)
    pm.register(Plugin1())
    pm.register(Plugin2())

    result = pm.hook.myhook(arg="test")
    assert result == "plugin2: test"


def test_historic_hook_configuration() -> None:
    pm = PluginManager("test")
    hookspec = HookspecMarker("test")
    hookimpl = HookimplMarker("test")

    results: list[str] = []

    class MySpec:
        @hookspec(historic=True)
        def myhook(self, arg: object) -> None:
            pass

    pm.add_hookspecs(MySpec)
    pm.hook.myhook.call_historic(
        kwargs={"arg": "call1"}, result_callback=results.append
    )

    class Plugin1:
        @hookimpl
        def myhook(self, arg: object) -> str:
            return f"plugin1: {arg}"

    pm.register(Plugin1())
    assert "plugin1: call1" in results
