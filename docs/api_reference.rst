:orphan:

API Reference
=============

.. autoclass:: pluggy.PluginManager
    :members:

.. autoclass:: pluggy.PluginValidationError
    :show-inheritance:
    :members:

.. autodecorator:: pluggy.HookspecMarker

.. autodecorator:: pluggy.HookimplMarker

.. autoclass:: pluggy.Result()
    :show-inheritance:
    :members:

.. autoclass:: pluggy.HookCaller()
    :members:
    :special-members: __call__

.. autoclass:: pluggy.HookCallError()
    :show-inheritance:
    :members:

.. autoclass:: pluggy.HookRelay()
    :members:

    .. data:: <hook name>

        :type: HookCaller

        The caller for the hook with the given name.
