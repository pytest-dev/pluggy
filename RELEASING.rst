Release Procedure
-----------------

Releases are largely automated via GitHub Actions.  The version is derived
automatically from changelog fragment types using the ``towncrier-fragments``
version scheme (``feature`` → minor, ``bugfix`` → patch, ``removal`` → major).

Automated flow
~~~~~~~~~~~~~~

#. Contributors add changelog fragments (``changelog/<id>.<type>.rst``) in
   their pull requests as usual.

#. Every push to ``main`` triggers the ``prepare-release`` workflow, which:

   * Computes the next version from the fragment types.
   * Creates (or force-updates) a ``release-X.Y.Z`` branch with the
     towncrier-built ``CHANGELOG.rst`` committed.
   * Opens (or updates) a PR targeting ``main``.

#. The normal CI (``test`` workflow) runs on the release PR.  Once all checks
   pass, the built wheel and sdist are uploaded to a **draft GitHub release**.

#. A maintainer reviews the PR and, when satisfied, **publishes the draft
   release** in the GitHub UI.

#. Publishing the release triggers the ``deploy`` workflow, which:

   * Verifies all PR checks are green.
   * Downloads the release assets (bit-identical to the draft).
   * Uploads them to PyPI via trusted publishing.
   * Merges the release PR into ``main``.
   * Cleans up the release branch.

Downstream testing
~~~~~~~~~~~~~~~~~~

Before publishing a release, consider running downstream integration tests::

    uv run downstream/run_downstream.py <recipe>

Use ``--list`` to discover available recipes.

Manual fallback
~~~~~~~~~~~~~~~

For local testing or exceptional situations, the legacy script is still
available::

    tox -e release -- VERSION

This creates a ``release-VERSION`` branch with the changelog committed,
ready to be pushed and opened as a PR manually.
