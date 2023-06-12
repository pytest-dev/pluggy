import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sphinx.application

if sys.version_info >= (3, 8):
    from importlib import metadata
else:
    import importlib_metadata as metadata


extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",
    "sphinx.ext.coverage",
    "sphinx.ext.viewcode",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

source_suffix = ".rst"

# The master toctree document.
master_doc = "index"

# General information about the project.

project = "pluggy"
copyright = "2016, Holger Krekel"
author = "Holger Krekel"

release = metadata.version(project)
# The short X.Y version.
version = ".".join(release.split(".")[:2])


language = "en"

pygments_style = "sphinx"
# html_logo = "_static/img/plug.png"
html_theme = "alabaster"
html_theme_options = {
    "logo": "img/plug.png",
    "description": "The pytest plugin system",
    "github_user": "pytest-dev",
    "github_repo": "pluggy",
    "github_button": "true",
    "github_banner": "true",
    "github_type": "star",
    "badge_branch": "master",
    "page_width": "1080px",
    "fixed_sidebar": "false",
}
html_sidebars = {
    "**": ["about.html", "localtoc.html", "relations.html", "searchbox.html"]
}
html_static_path = ["_static"]

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [(master_doc, "pluggy", "pluggy Documentation", [author], 1)]

autodoc_typehints = "none"

# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        "pluggy",
        "pluggy Documentation",
        author,
        "pluggy",
        "One line description of project.",
        "Miscellaneous",
    )
]

# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pytest": ("https://docs.pytest.org/en/latest", None),
    "setuptools": ("https://setuptools.readthedocs.io/en/latest", None),
    "tox": ("https://tox.readthedocs.io/en/latest", None),
    "devpi": ("https://devpi.net/docs/devpi/devpi/stable/+doc/", None),
    "kedro": ("https://kedro.readthedocs.io/en/latest/", None),
}


def configure_logging(app: "sphinx.application.Sphinx") -> None:
    """Configure Sphinx's WarningHandler to handle (expected) missing include."""
    import sphinx.util.logging
    import logging

    class WarnLogFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            """Ignore warnings about missing include with "only" directive.

            Ref: https://github.com/sphinx-doc/sphinx/issues/2150."""
            if (
                record.msg.startswith('Problems with "include" directive path:')
                and "_changelog_towncrier_draft.rst" in record.msg
            ):
                return False
            return True

    logger = logging.getLogger(sphinx.util.logging.NAMESPACE)
    warn_handler = [x for x in logger.handlers if x.level == logging.WARNING]
    assert len(warn_handler) == 1, warn_handler
    warn_handler[0].filters.insert(0, WarnLogFilter())


def setup(app: "sphinx.application.Sphinx") -> None:
    configure_logging(app)
