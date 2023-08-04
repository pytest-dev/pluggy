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

.. autoclass:: pluggy._result._Result()
    :show-inheritance:
    :members:

.. autoclass:: pluggy._hooks._HookCaller()
    :members:
    :special-members: __call__

.. autoclass:: pluggy.HookCallError()
    :show-inheritance:
    :members:

.. autoclass:: pluggy._hooks._HookRelay()
    :members:

    .. data:: <hook name>

        :type: _HookCaller

        The caller for the hook with the given name.
