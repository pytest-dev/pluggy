``pluggy``
==========

The ``pytest`` plugin system
----------------------------
``pluggy`` is the crystallized core of `plugin management and hook
calling`_ for `pytest`_.

In fact, ``pytest`` is itself composed as a set of ``pluggy`` plugins
which are invoked in sequence according to a well defined set of protocols.
Some `200+ plugins`_ use ``pluggy`` to extend and customize ``pytest``'s default behaviour.

In essence, ``pluggy`` enables function `hooking`_ so you can build "pluggable" systems.

How's it work?
--------------
A `plugin` is a `namespace`_ which defines hook functions.

``pluggy`` manages *plugins* by relying on:

- a hook *specification* - defines a call signature
- a set of hook *implementations* - aka `callbacks`_
- the hook *caller* - a call loop which collects results

where for each registered hook *specification*, a hook *call* will invoke up to ``N``
registered hook *implementations*.

``pluggy`` accomplishes all this by implementing a `request-response pattern`_ using *function*
subscriptions and can be thought of and used as a rudimentary busless `publish-subscribe`_
event system.

``pluggy``'s approach is meant to let a designer think carefuly about which objects are
explicitly needed by an extension writer. This is in contrast to subclass-based extension
systems which may expose unecessary state and behaviour or encourage `tight coupling`_
in overlying frameworks.


A first example
---------------

.. literalinclude:: examples/firstexample.py

Running this directly gets us::

    $ python docs/examples/example1.py

    inside Plugin_2.myhook()
    inside Plugin_1.myhook()
    [-1, 3]

For more details and advanced usage see our

User Guide
----------
.. toctree::
   :maxdepth: 1

   define
   manage
   calling
   tracing
   api_reference

.. tracing

Development
-----------
Great care must taken when hacking on ``pluggy`` since multiple mature
projects rely on it. Our Github integrated CI process runs the full
`tox test suite`_ on each commit so be sure your changes can run on
all required `Python interpreters`_ and ``pytest`` versions.

Release Policy
**************
Pluggy uses `Semantic Versioning`_. Breaking changes are only foreseen for
Major releases (incremented X in "X.Y.Z").  If you want to use ``pluggy``
in your project you should thus use a dependency restriction like
``"pluggy>=0.1.0,<1.0"`` to avoid surprises.


.. hyperlinks
.. _pytest:
    http://pytest.org
.. _request-response pattern:
    https://en.wikipedia.org/wiki/Request%E2%80%93response
.. _publish-subscribe:
    https://en.wikipedia.org/wiki/Publish%E2%80%93subscribe_pattern
.. _hooking:
    https://en.wikipedia.org/wiki/Hooking
.. _plugin management and hook calling:
    http://doc.pytest.org/en/latest/writing_plugins.html
.. _namespace:
    https://docs.python.org/3.6/tutorial/classes.html#python-scopes-and-namespaces
.. _callbacks:
    https://en.wikipedia.org/wiki/Callback_(computer_programming)
.. _tox test suite:
    https://github.com/pytest-dev/pluggy/blob/master/tox.ini
.. _Semantic Versioning:
    http://semver.org/
.. _tight coupling:
    https://en.wikipedia.org/wiki/Coupling_%28computer_programming%29#Types_of_coupling
.. _Python interpreters:
    https://github.com/pytest-dev/pluggy/blob/master/tox.ini#L2
.. _200+ plugins:
    http://plugincompat.herokuapp.com/


.. Indices and tables
.. ==================
.. * :ref:`genindex`
.. * :ref:`modindex`
.. * :ref:`search`
