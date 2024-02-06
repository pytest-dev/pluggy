====================================================
ln_pluggy - A minimalist production ready plugin system
====================================================


A definitive example
--------------------
.. code-block:: python

    import ln_pluggy

    hookspec = ln_pluggy.HookspecMarker("myproject")
    hookimpl = ln_pluggy.HookimplMarker("myproject")


    class MySpec:
        """A hook specification namespace."""

        @hookspec
        def myhook(self, arg1, arg2):
            """My special little hook that you can customize."""


    class Plugin_1:
        """A hook implementation namespace."""

        @hookimpl
        def myhook(self, arg1, arg2):
            print("inside Plugin_1.myhook()")
            return arg1 + arg2


    class Plugin_2:
        """A 2nd hook implementation namespace."""

        @hookimpl
        def myhook(self, arg1, arg2):
            print("inside Plugin_2.myhook()")
            return arg1 - arg2


    # create a manager and add the spec
    pm = ln_pluggy.PluginManager("myproject")
    pm.add_hookspecs(MySpec)

    # register plugins
    pm.register(Plugin_1())
    pm.register(Plugin_2())

    # call our ``myhook`` hook
    results = pm.hook.myhook(arg1=1, arg2=2)
    print(results)


Running this directly gets us::

    $ python docs/examples/toy-example.py
    inside Plugin_2.myhook()
    inside Plugin_1.myhook()
    [-1, 3]


