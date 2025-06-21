"""
Tests for ProjectSpec functionality.
"""

from pluggy import HookimplMarker
from pluggy import HookspecMarker
from pluggy import PluginManager
from pluggy import ProjectSpec


def test_project_spec_basic_creation() -> None:
    """Test basic ProjectSpec creation and properties."""
    project = ProjectSpec("testproject")

    assert project.project_name == "testproject"
    assert isinstance(project.hookspec, HookspecMarker)
    assert isinstance(project.hookimpl, HookimplMarker)
    assert project.hookspec.project_name == "testproject"
    assert project.hookimpl.project_name == "testproject"


def test_project_spec_plugin_manager_creation() -> None:
    """Test that create_plugin_manager returns fresh instances."""
    project = ProjectSpec("testproject")

    pm1 = project.create_plugin_manager()
    pm2 = project.create_plugin_manager()

    # Should be different instances
    assert pm1 is not pm2

    # But should have same project name
    assert pm1.project_name == "testproject"
    assert pm2.project_name == "testproject"

    # Should be PluginManager instances
    assert isinstance(pm1, PluginManager)
    assert isinstance(pm2, PluginManager)


def test_project_spec_custom_plugin_manager_class() -> None:
    """Test ProjectSpec with custom PluginManager subclass."""

    class CustomPluginManager(PluginManager):
        def __init__(self, project_name: str) -> None:
            super().__init__(project_name)
            self.custom_attr = "custom_value"

    project = ProjectSpec("testproject", plugin_manager_cls=CustomPluginManager)
    pm = project.create_plugin_manager()

    assert isinstance(pm, CustomPluginManager)
    assert pm.project_name == "testproject"
    assert hasattr(pm, "custom_attr")
    assert pm.custom_attr == "custom_value"


def test_project_spec_functional_integration() -> None:
    """Test that ProjectSpec components work together functionally."""
    project = ProjectSpec("testproject")

    hookspec = project.hookspec
    hookimpl = project.hookimpl

    # Define a hook spec
    class HookSpecs:
        @hookspec
        def my_hook(self, arg: int) -> int:  # type: ignore[empty-body]
            ...

    # Define a plugin with hook implementation
    class Plugin:
        @hookimpl
        def my_hook(self, arg: int) -> int:
            return arg * 2

    # Create plugin manager and test integration
    pm = project.create_plugin_manager()
    pm.add_hookspecs(HookSpecs)
    pm.register(Plugin())

    # Test hook calling
    result = pm.hook.my_hook(arg=5)
    assert result == [10]


def test_project_spec_multiple_plugin_managers_independent() -> None:
    """Test that multiple PluginManager instances are independent."""
    project = ProjectSpec("testproject")

    pm1 = project.create_plugin_manager()
    pm2 = project.create_plugin_manager()

    # Register different plugins on each manager
    class Plugin1:
        pass

    class Plugin2:
        pass

    pm1.register(Plugin1(), name="plugin1")
    pm2.register(Plugin2(), name="plugin2")

    # Each manager should only have its own plugin
    assert pm1.has_plugin("plugin1")
    assert not pm1.has_plugin("plugin2")
    assert pm2.has_plugin("plugin2")
    assert not pm2.has_plugin("plugin1")


def test_project_spec_different_project_names() -> None:
    """Test that different ProjectSpecs have different project names."""
    project1 = ProjectSpec("project1")
    project2 = ProjectSpec("project2")

    assert project1.project_name == "project1"
    assert project2.project_name == "project2"
    assert project1.hookspec.project_name == "project1"
    assert project2.hookspec.project_name == "project2"
    assert project1.hookimpl.project_name == "project1"
    assert project2.hookimpl.project_name == "project2"


def test_project_spec_hook_attribute_naming() -> None:
    """Test that hook attributes are created with correct project names."""
    project = ProjectSpec("myproject")

    hookspec = project.hookspec
    hookimpl = project.hookimpl

    # Create test functions
    @hookspec
    def test_hook() -> None:
        pass

    @hookimpl
    def test_hook_impl() -> None:
        pass

    # Check that attributes are set with correct project name
    assert hasattr(test_hook, "myproject_spec")
    assert hasattr(test_hook_impl, "myproject_impl")


def test_project_spec_with_get_hookconfig() -> None:
    """Test that ProjectSpec works with get_hookimpl_config()."""
    project = ProjectSpec("testproject")
    hookimpl = project.hookimpl

    # Create a decorated function
    @hookimpl(tryfirst=True, optionalhook=True)
    def my_hook_impl() -> None:
        pass

    # Get the configuration using ProjectSpec
    config = project.get_hookimpl_config(my_hook_impl)

    assert config is not None
    assert config.tryfirst is True
    assert config.optionalhook is True
    assert config.wrapper is False
    assert config.hookwrapper is False
    assert config.trylast is False


def test_marker_classes_accept_project_spec() -> None:
    """Test that marker classes can accept ProjectSpec instances."""
    project = ProjectSpec("testproject")

    # Test creating markers with ProjectSpec instance
    hookspec_from_project = HookspecMarker(project)
    hookimpl_from_project = HookimplMarker(project)

    # Should have same project name
    assert hookspec_from_project.project_name == "testproject"
    assert hookimpl_from_project.project_name == "testproject"

    # Should store the ProjectSpec reference
    assert hookspec_from_project._project_spec is project
    assert hookimpl_from_project._project_spec is project


def test_marker_classes_accept_string() -> None:
    """Test that marker classes still work with string project names."""
    # Test creating markers with string (legacy behavior)
    hookspec_from_string = HookspecMarker("testproject")
    hookimpl_from_string = HookimplMarker("testproject")

    # Should have correct project name
    assert hookspec_from_string.project_name == "testproject"
    assert hookimpl_from_string.project_name == "testproject"

    # Should have created internal ProjectSpec instances
    assert hookspec_from_string._project_spec is not None
    assert hookimpl_from_string._project_spec is not None
    assert hookspec_from_string._project_spec.project_name == "testproject"
    assert hookimpl_from_string._project_spec.project_name == "testproject"


def test_plugin_manager_accepts_project_spec() -> None:
    """Test that PluginManager can accept ProjectSpec instances."""
    project = ProjectSpec("testproject")

    # Test creating PluginManager with ProjectSpec instance
    pm_from_project = PluginManager(project)

    # Should have same project name
    assert pm_from_project.project_name == "testproject"

    # Should store the ProjectSpec reference
    assert pm_from_project._project_spec is project


def test_plugin_manager_accepts_string() -> None:
    """Test that PluginManager still works with string project names."""
    # Test creating PluginManager with string (legacy behavior)
    pm_from_string = PluginManager("testproject")

    # Should have correct project name
    assert pm_from_string.project_name == "testproject"

    # Should have created internal ProjectSpec instance
    assert pm_from_string._project_spec is not None
    assert pm_from_string._project_spec.project_name == "testproject"


def test_project_name_is_property() -> None:
    """Test that project_name is now a property that delegates to ProjectSpec."""
    project = ProjectSpec("testproject")

    # Test with markers created from ProjectSpec
    hookspec = project.hookspec
    hookimpl = project.hookimpl
    pm = project.create_plugin_manager()

    # All should have same project name via property
    assert hookspec.project_name == "testproject"
    assert hookimpl.project_name == "testproject"
    assert pm.project_name == "testproject"

    # Test with markers created from string
    hookspec_str = HookspecMarker("anotherproject")
    hookimpl_str = HookimplMarker("anotherproject")
    pm_str = PluginManager("anotherproject")

    # All should have correct project name via property
    assert hookspec_str.project_name == "anotherproject"
    assert hookimpl_str.project_name == "anotherproject"
    assert pm_str.project_name == "anotherproject"
