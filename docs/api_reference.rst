:orphan:

.. _`api-reference`:

API Reference
=============

.. autoclass:: ln_pluggy.PluginManager
    :members:

.. autoclass:: ln_pluggy.PluginValidationError
    :show-inheritance:
    :members:

.. autodecorator:: ln_pluggy.HookspecMarker

.. autodecorator:: ln_pluggy.HookimplMarker

.. autoclass:: ln_pluggy.HookRelay()
    :members:

    .. data:: <hook name>

        :type: HookCaller

        The caller for the hook with the given name.

.. autoclass:: ln_pluggy.HookCaller()
    :members:
    :special-members: __call__

.. autoclass:: ln_pluggy.HookCallError()
    :show-inheritance:
    :members:

.. autoclass:: ln_pluggy.Result()
    :show-inheritance:
    :members:

.. autoclass:: ln_pluggy.HookImpl()
    :members:

.. autoclass:: ln_pluggy.HookspecOpts()
    :show-inheritance:
    :members:

.. autoclass:: ln_pluggy.HookimplOpts()
    :show-inheritance:
    :members:


Warnings
--------

Custom warnings generated in some situations such as improper usage or deprecated features.

.. autoclass:: ln_pluggy.PluggyWarning()
    :show-inheritance:

.. autoclass:: ln_pluggy.PluggyTeardownRaisedWarning()
    :show-inheritance:
