The Plugin Registry
===================
``pluggy`` manages plugins using instances of the
:py:class:`pluggy.PluginManager`.

A ``PluginManager`` is instantiated with a single
``str`` argument, the ``project_name``:

.. code-block:: python

    import pluggy
    pm = pluggy.PluginManager('my_project_name')


The ``project_name`` value is used when a ``PluginManager`` scans for *hook*
functions :doc:`defined on a plugin <define>`.
This allows for multiple
plugin managers from multiple projects to define hooks alongside each other.


Registration
------------
Each ``PluginManager`` maintains a *plugin* registry where each *plugin*
contains a set of *hookimpl* definitions. Loading *hookimpl* and *hookspec*
definitions to populate the registry is described in detail in the section on
:doc:`define`.

In summary, you pass a plugin namespace object to the
:py:meth:`~pluggy.PluginManager.register()` and
:py:meth:`~pluggy.PluginManager.add_hookspec()` methods to collect
hook *implementations* and *specfications* from *plugin* namespaces respectively.

You can unregister any *plugin*'s hooks using
:py:meth:`~pluggy.PluginManager.unregister()` and check if a plugin is
registered by passing its name to the
:py:meth:`~pluggy.PluginManager.is_registered()` method.

Loading ``setuptools`` entry points
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
You can automatically load plugins registered through `setuptools entry points`_
with the :py:meth:`~pluggy.PluginManager.load_setuptools_entrypoints()`
method.

An example use of this is the `pytest entry point`_.


Blocking
--------
You can block any plugin from being registered using
:py:meth:`~pluggy.PluginManager.set_blocked()` and check if a given
*plugin* is blocked by name using :py:meth:`~pluggy.PluginManager.is_blocked()`.


Inspection
----------
You can use a variety of methods to inspect the both the registry
and particular plugins in it:

- :py:meth:`~pluggy.PluginManager.list_name_plugin()` -
  return a list of name-plugin pairs
- :py:meth:`~pluggy.PluginManager.get_plugins()` - retrieve all plugins
- :py:meth:`~pluggy.PluginManager.get_canonical_name()`- get a *plugin*'s
  canonical name (the name it was registered with)
- :py:meth:`~pluggy.PluginManager.get_plugin()` - retrieve a plugin by its
  canonical name

Parsing mark options
^^^^^^^^^^^^^^^^^^^^
You can retrieve the *options* applied to a particular
*hookspec* or *hookimpl* as per :ref:`marking_hooks` using the
:py:meth:`~pluggy.PluginManager.parse_hookspec_opts()` and
:py:meth:`~pluggy.PluginManager.parse_hookimpl_opts()` respectively.

.. links
.. _setuptools entry points:
    http://setuptools.readthedocs.io/en/latest/setuptools.html#dynamic-discovery-of-services-and-plugins
.. _pytest entry point:
    http://doc.pytest.org/en/latest/writing_plugins.html#setuptools-entry-points
