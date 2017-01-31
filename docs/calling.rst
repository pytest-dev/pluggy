Calling Hooks
=============
The core functionality of ``pluggy`` enables an extension provider
to override function calls made at certain points throughout a program.

A particular *hook* is invoked by calling an instance of
a :py:class:`pluggy._HookCaller` which in turn *loops* through the
``1:N`` registered *hookimpls* and calls them in sequence.

Every :py:class:`pluggy.PluginManager` has a ``hook`` attribute
which is an instance of a :py:class:`pluggy._HookRelay`.
The ``_HookRelay`` itself contains references (by hook name) to each
registered *hookimpl*'s ``_HookCaller`` instance.

More practically you call a *hook* like so:

.. code-block:: python

    import sys
    import pluggy
    import mypluginspec
    import myplugin
    from configuration import config

    pm = pluggy.PluginManager("myproject")
    pm.add_hookspecs(mypluginspec)
    pm.register(myplugin)

    # we invoke the _HookCaller and thus all underlying hookimpls
    result_list = pm.hook.myhook(config=config, args=sys.argv)

Note that you **must** call hooks using keyword `arguments`_ syntax!


Collecting results
------------------
By default calling a hook results in all underlying :ref:`hookimpls
<impls>` functions to be invoked in sequence via a loop. Any function
which returns a value other then a ``None`` result will have that result
appended to a :py:class:`list` which is returned by the call.

The only exception to this behaviour is if the hook has been marked to return
its :ref:`firstresult` in which case only the first single value (which is not
``None``) will be returned.

.. _call_historic:

Historic calls
--------------
A *historic call* allows for all newly registered functions to receive all hook
calls that happened before their registration. The implication is that this is
only useful if you expect that some *hookimpls* may be registered **after** the
hook is initially invoked.

Historic hooks must be :ref:`specially marked <historic>` and called
using the :py:meth:`pluggy._HookCaller.call_historic()` method:

.. code-block:: python

    # call with history; no results returned
    pm.hook.myhook.call_historic(config=config, args=sys.argv)

    # ... more of our program ...

    # late loading of some plugin
    import mylateplugin

    # historic call back is done here
    pm.register(mylateplugin)

Note that if you ``call_historic()`` the ``_HookCaller`` (and thus your
calling code) can not receive results back from the underlying *hookimpl*
functions.

Calling with extras
-------------------
You can call a hook with temporarily participating *implementation* functions
(that aren't in the registry) using the
:py:meth:`pluggy._HookCaller.call_extra()` method.


Calling with a subset of registered plugins
-------------------------------------------
You can make a call using a subset of plugins by asking the
``PluginManager`` first for a ``_HookCaller`` with those plugins removed
using the :py:meth:`pluggy.PluginManger.subset_hook_caller()` method.

You then can use that ``_HookCaller`` to make normal, ``call_historic()``,
or ``call_extra()`` calls as necessary.


.. links
.. _arguments:
    https://docs.python.org/3/glossary.html#term-argument
