0.5.0
-----

- fix bug where callbacks for historic hooks would not be called for
  already registered plugins.  Thanks `@vodik`_ for the PR
  and `@hpk42`_ for further fixes.

- fix `#17`_ by considering only actual functions for hooks
  this removes the ability to register arbitrary callable objects
  which at first glance is a reasonable simplification,
  thanks `@RonnyPfannschmidt`_ for report and pr.

- fix `#9`_: allow registering hookspecs from instances.  The PR from
  `@tgoodlet`_ also modernized the varnames implementation.


.. _#9: https://github.com/pytest-dev/pytest/issues/9
.. _#17: https://github.com/pytest-dev/pytest/issues/17

.. _@tgoodlet: https://github.com/tgoodlet
.. _@vodik: https://github.com/vodik
.. _@RonnyPfannschmidt: https://github.com/RonnyPfannschmidt


0.4.0
-----

- add ``has_plugin(name)`` method to pluginmanager.  thanks `@nicoddemus`_.

- fix `#11`_: make plugin parsing more resilient against exceptions
  from ``__getattr__`` functions. Thanks `@nicoddemus`_.

- fix issue `#4`_: specific ``HookCallError`` exception for when a hook call
  provides not enough arguments.

- better error message when loading setuptools entrypoints fails
  due to a ``VersionConflict``.  Thanks `@blueyed`_.

.. _#11: https://github.com/pytest-dev/pytest/issues/11
.. _#4: https://github.com/pytest-dev/pytest/issues/4

.. _@blueyed: https://github.com/blueyed
.. _@nicoddemus: https://github.com/nicoddemus


0.3.1
-----

- avoid using deprecated-in-python3.5 getargspec method. Thanks 
  `@mdboom`_.

.. _@mdboom: https://github.com/mdboom

0.3.0
-----

initial release

.. _@hpk42: https://github.com/hpk42


