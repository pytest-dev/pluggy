Defining and Collecting Hooks
=============================
A *plugin* is a namespace type (currently one of a ``class`` or module)
which defines a set of *hook* functions.

As mentioned in :doc:`manage`, all *plugins* which define *hooks*
are managed by an instance of a :py:class:`pluggy.PluginManager` which
defines the primary ``pluggy`` API.

In order for a ``PluginManager`` to detect functions in a namespace
intended to be *hooks*, they must be decorated using special ``pluggy`` *marks*.

.. _marking_hooks:

Marking hooks
-------------
The :py:class:`~pluggy.HookspecMarker` and :py:class:`~pluggy.HookimplMarker`
decorators are used to *mark* functions for detection by a ``PluginManager``:

.. code-block:: python

    from pluggy import HookspecMarker, HookimplMarker

    hookspec = HookspecMarker('project_name')
    hookimpl = HookimplMarker('project_name')


Each decorator type takes a single ``project_name`` string as its
lone argument the value of which is used to mark hooks for detection by
by a similarly configured ``PluginManager`` instance.

That is, a *mark* type called with ``project_name`` returns an object which
can be used to decorate functions which will then be detected by a
``PluginManager`` which was instantiated with the the same ``project_name``
value.

Furthermore, each *hookimpl* or *hookspec* decorator can configure the
underlying call-time behavior of each *hook* object by providing special
*options* passed as keyword arguments.


.. note::
    The following sections correspond to similar documentation in
    ``pytest`` for `Writing hook functions`_ and can be used
    as a supplementary resource.

.. _impls:

Implementations
---------------
A hook *implementation* (*hookimpl*) is just a (callback) function
which has been appropriately marked.

*hookimpls* are loaded from a plugin using the
:py:meth:`~pluggy.PluginManager.register()` method:

.. code-block:: python

    import sys
    from pluggy import PluginManager, HookimplMarker

    hookimpl = HookimplMarker('myproject')

    @hookimpl
    def setup_project(config, args):
        """This hook is used to process the initial config
        and possibly input arguments.
        """
        if args:
            config.process_args(args)

        return config

    pm = PluginManager('myproject')

    # load all hookimpls from the local module's namespace
    plugin_name = pm.register(sys.modules[__name__])

.. _optionalhook:

Optional validation
^^^^^^^^^^^^^^^^^^^
Normally each *hookimpl* should be validated a against a corresponding
hook :ref:`specification <specs>`. If you want to make an exception
then the *hookimpl* should be marked with the ``"optionalhook"`` option:

.. code-block:: python

    @hookimpl(optionalhook=True)
    def setup_project(config, args):
        """This hook is used to process the initial config
        and possibly input arguments.
        """
        if args:
            config.process_args(args)

        return config

Call time order
^^^^^^^^^^^^^^^
A *hookimpl* can influence its call-time invocation position.
If marked with a ``"tryfirst"`` or ``"trylast"`` option it will be
executed *first* or *last* respectively in the hook call loop:

.. code-block:: python

    import sys
    from pluggy import PluginManager, HookimplMarker

    hookimpl = HookimplMarker('myproject')

    @hookimpl(trylast=True)
    def setup_project(config, args):
        """Default implementation.
        """
        if args:
            config.process_args(args)

        return config


    class SomeOtherPlugin(object):
        """Some other plugin defining the same hook.
        """
        @hookimpl(tryfirst=True)
        def setup_project(config, args):
            """Report what args were passed before calling
            downstream hooks.
            """
            if args:
                print("Got args: {}".format(args))

            return config

    pm = PluginManager('myproject')

    # load from the local module's namespace
    pm.register(sys.modules[__name__])
    # load a plugin defined on a class
    pm.register(SomePlugin())

For another example see the `hook function ordering`_ section of the
``pytest`` docs.

Wrappers
^^^^^^^^
A *hookimpl* can be marked with a ``"hookwrapper"`` option which indicates that
the function will be called to *wrap* (or surround) all other normal *hookimpl*
calls. A *hookwrapper* can thus execute some code ahead and after the execution
of all corresponding non-hookwrappper *hookimpls*.

Much in the same way as a `@contextlib.contextmanager`_, *hookwrappers* must
be implemented as generator function with a single ``yield`` in its body:


.. code-block:: python

    @hookimpl(hookwrapper=True)
    def setup_project(config, args):
        """Wrap calls to ``setup_project()`` implementations which
        should return json encoded config options.
        """
        if config.debug:
            print("Pre-hook config is {}".format(
                config.tojson()))

        # get initial default config
        defaults = config.tojson()

        # all corresponding hookimpls are invoked here
        outcome = yield

        for item in outcome.get_result():
            print("JSON config override is {}".format(item))

        if config.debug:
            print("Post-hook config is {}".format(
                config.tojson()))

        if config.use_defaults:
            outcome.force_result(defaults)

The generator is `sent`_ a :py:class:`pluggy._CallOutcome` object which can
be assigned in the ``yield`` expression and used to override or inspect
the final result(s) returned back to the hook caller. 

.. note::
    Hook wrappers can **not** return results (as per generator function
    semantics); they can only modify them using the ``_CallOutcome`` API.

Also see the `hookwrapper`_ section in the ``pytest`` docs.

.. _specs:

Specifications
--------------
A hook *specification* (*hookspec*) is a definition used to validate each
*hookimpl* ensuring that an extension writer has correctly defined their
callback function *implementation* .

*hookspecs* are defined using similarly marked functions however only the
function *signature* (its name and names of all its arguments) is analyzed
and stored. As such, often you will see a *hookspec* defined with only
a docstring in its body.

*hookspecs* are loaded using the
:py:meth:`~pluggy.PluginManager.add_hookspecs()` method and normally
should be added before registering corresponding *hookimpls*:

.. code-block:: python

    import sys
    from pluggy import PluginManager, HookspecMarker

    hookspec = HookspecMarker('myproject')

    @hookspec
    def setup_project(config, args):
        """This hook is used to process the inital config and input
        arguments.
        """

    pm = PluginManager('myproject')

    # load from the local module's namespace
    pm.add_hookspecs(sys.modules[__name__])


Registering a *hookimpl* which does not meet the constraints of its
corresponding *hookspec* will result in an error.

A *hookspec* can also be added **after** some *hookimpls* have been
registered however this is not normally recommended as it results in
delayed hook validation.

.. note::
    The term *hookspec* can sometimes refer to the plugin-namespace
    which defines ``hookspec`` decorated functions as in the case of
    ``pytest``'s `hookspec module`_

Enforcing spec validation
^^^^^^^^^^^^^^^^^^^^^^^^^
By default there is no strict requirement that each *hookimpl* has
a corresponding *hookspec*. However, if you'd like you enforce this
behavior you can run a check with the
:py:meth:`~pluggy.PluginManager.check_pending()` method. If you'd like
to enforce requisite *hookspecs* but with certain exceptions for some hooks
then make sure to mark those hooks as :ref:`optional <optionalhook>`.

Opt-in arguments
^^^^^^^^^^^^^^^^
To allow for *hookspecs* to evolve over the lifetime of a project,
*hookimpls* can accept **less** arguments then defined in the spec.
This allows for extending hook arguments (and thus semantics) without
breaking existing *hookimpls*.

In other words this is ok:

.. code-block:: python

    @hookspec
    def myhook(config, args):
        pass

    @hookimpl
    def myhook(args):
        print(args)


whereas this is not:

.. code-block:: python

    @hookspec
    def myhook(config, args):
        pass

    @hookimpl
    def myhook(config, args, extra_arg):
        print(args)

.. _firstresult:

First result only
^^^^^^^^^^^^^^^^^
A *hookspec* can be marked such that when the *hook* is called the call loop
will only invoke up to the first *hookimpl* which returns a result other
then ``None``.

.. code-block:: python

    @hookspec(firstresult=True)
    def myhook(config, args):
        pass

This can be useful for optimizing a call loop for which you are only
interested in a single core *hookimpl*. An example is the
`pytest_cmdline_main`_ central routine of ``pytest``.

Also see the `first result`_ section in the ``pytest`` docs.

.. _historic:

Historic hooks
^^^^^^^^^^^^^^
You can mark a *hookspec* as being *historic* meaning that the hook
can be called with :py:meth:`~pluggy.PluginManager.call_historic()` **before**
having been registered:

.. code-block:: python

    @hookspec(historic=True)
    def myhook(config, args):
        pass

The implication is that late registered *hookimpls* will be called back
immediately at register time and **can not** return a result to the caller.**

This turns out to be particularly useful when dealing with lazy or
dynamically loaded plugins.

For more info see :ref:`call_historic`.


.. links
.. _@contextlib.contextmanager:
    https://docs.python.org/3.6/library/contextlib.html#contextlib.contextmanager
.. _pytest_cmdline_main:
    https://github.com/pytest-dev/pytest/blob/master/_pytest/hookspec.py#L80
.. _hookspec module:
    https://github.com/pytest-dev/pytest/blob/master/_pytest/hookspec.py
.. _Writing hook functions:
    http://doc.pytest.org/en/latest/writing_plugins.html#writing-hook-functions
.. _hookwrapper:
    http://doc.pytest.org/en/latest/writing_plugins.html#hookwrapper-executing-around-other-hooks
.. _hook function ordering:
    http://doc.pytest.org/en/latest/writing_plugins.html#hook-function-ordering-call-example
.. _first result:
    http://doc.pytest.org/en/latest/writing_plugins.html#firstresult-stop-at-first-non-none-result
.. _sent:
    https://docs.python.org/3/reference/expressions.html#generator.send
