Release Procedure
-----------------

#. Update the ``CHANGELOG.rst`` for the new release and commit.

#. Open a PR named ``release-X.Y.Z`` targeting ``master``.

#. All tests must pass and the PR must be approved by at least another maintainer.

#. Publish to PyPI by pushing a tag::

     git tag X.Y.Z release-X.Y.Z
     git push git@github.com:pytest-dev/pluggy.git X.Y.Z

   The tag will trigger a new build, which will deploy to PyPI.

#. Make sure it is `available on PyPI <https://pypi.org/project/pluggy>`_.

#. Merge ``release-X.Y.Z`` into ``master``, either manually or using GitHub's web interface.

