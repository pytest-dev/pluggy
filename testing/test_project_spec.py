"""
Tests for ProjectSpec functionality.
"""

from __future__ import annotations

from pluggy import HookimplMarker
from pluggy import HookspecMarker
from pluggy import PluginManager
from pluggy import ProjectSpec


def test_project_spec_basic_creation() -> None:
    project = ProjectSpec("testproject")

    assert project.project_name == "testproject"
    assert isinstance(project.hookspec, HookspecMarker)
    assert isinstance(project.hookimpl, HookimplMarker)
    assert project.hookspec.project_name == "testproject"
    assert project.hookimpl.project_name == "testproject"
    assert repr(project) == "ProjectSpec(project_name='testproject')"


def test_project_spec_plugin_manager_creation() -> None:
    project = ProjectSpec("testproject")

    pm1 = project.create_plugin_manager()
    pm2 = project.create_plugin_manager()

    assert pm1 is not pm2
    assert pm1.project_name == "testproject"
    assert pm2.project_name == "testproject"
    assert isinstance(pm1, PluginManager)
    assert isinstance(pm2, PluginManager)


def test_project_spec_custom_plugin_manager_class() -> None:
    class CustomPluginManager(PluginManager):
        def __init__(self, project_name: str | ProjectSpec) -> None:
            super().__init__(project_name)
            self.custom_attr = "custom_value"

    project = ProjectSpec("testproject", plugin_manager_cls=CustomPluginManager)
    pm = project.create_plugin_manager()

    assert isinstance(pm, CustomPluginManager)
    assert pm.project_name == "testproject"
    assert pm.custom_attr == "custom_value"


def test_project_spec_functional_integration() -> None:
    project = ProjectSpec("testproject")

    hookspec = project.hookspec
    hookimpl = project.hookimpl

    class HookSpecs:
        @hookspec
        def my_hook(self, arg: int) -> int:  # type: ignore[empty-body]
            ...

    class Plugin:
        @hookimpl
        def my_hook(self, arg: int) -> int:
            return arg * 2

    pm = project.create_plugin_manager()
    pm.add_hookspecs(HookSpecs)
    pm.register(Plugin())

    result = pm.hook.my_hook(arg=5)
    assert result == [10]


def test_project_spec_multiple_plugin_managers_independent() -> None:
    project = ProjectSpec("testproject")

    pm1 = project.create_plugin_manager()
    pm2 = project.create_plugin_manager()

    class Plugin1:
        pass

    class Plugin2:
        pass

    pm1.register(Plugin1(), name="plugin1")
    pm2.register(Plugin2(), name="plugin2")

    assert pm1.has_plugin("plugin1")
    assert not pm1.has_plugin("plugin2")
    assert pm2.has_plugin("plugin2")
    assert not pm2.has_plugin("plugin1")


def test_project_spec_hook_attribute_naming() -> None:
    project = ProjectSpec("myproject")

    @project.hookspec
    def test_hook() -> None:
        pass

    @project.hookimpl
    def test_hook_impl() -> None:
        pass

    assert hasattr(test_hook, "myproject_spec")
    assert hasattr(test_hook_impl, "myproject_impl")


def test_project_spec_get_hook_configs() -> None:
    project = ProjectSpec("testproject")

    @project.hookspec(firstresult=True)
    def my_hook() -> None:
        pass

    @project.hookimpl(tryfirst=True, optionalhook=True)
    def my_hook_impl() -> None:
        pass

    spec_config = project.get_hookspec_config(my_hook)
    assert spec_config is not None
    assert spec_config.firstresult is True

    impl_config = project.get_hookimpl_config(my_hook_impl)
    assert impl_config is not None
    assert impl_config.tryfirst is True
    assert impl_config.optionalhook is True
    assert impl_config.wrapper is False

    def undecorated() -> None:
        pass

    assert project.get_hookspec_config(undecorated) is None
    assert project.get_hookimpl_config(undecorated) is None


def test_marker_classes_accept_project_spec() -> None:
    project = ProjectSpec("testproject")

    hookspec_from_project = HookspecMarker(project)
    hookimpl_from_project = HookimplMarker(project)

    assert hookspec_from_project.project_name == "testproject"
    assert hookimpl_from_project.project_name == "testproject"
    assert hookspec_from_project._project_spec is project
    assert hookimpl_from_project._project_spec is project


def test_marker_classes_accept_string() -> None:
    hookspec_from_string = HookspecMarker("testproject")
    hookimpl_from_string = HookimplMarker("testproject")

    assert hookspec_from_string.project_name == "testproject"
    assert hookimpl_from_string.project_name == "testproject"
    assert hookspec_from_string._project_spec.project_name == "testproject"
    assert hookimpl_from_string._project_spec.project_name == "testproject"


def test_plugin_manager_accepts_project_spec() -> None:
    project = ProjectSpec("testproject")
    pm = PluginManager(project)

    assert pm.project_name == "testproject"
    assert pm._project_spec is project


def test_plugin_manager_accepts_string() -> None:
    pm = PluginManager("testproject")

    assert pm.project_name == "testproject"
    assert pm._project_spec.project_name == "testproject"
