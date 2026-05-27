"""Compute the next release version from setuptools_scm + towncrier fragments.

Uses the ``towncrier-fragments`` version scheme to derive a semver bump
from changelog fragment types, then strips the ``.devN+hash`` suffix to
produce a clean release version (e.g. ``1.7.0``).

Exits non-zero when no changelog fragments are present.
"""

from __future__ import annotations

from pathlib import Path
import sys


def _changelog_fragments(changelog_dir: Path) -> list[Path]:
    """Return fragment files, ignoring templates, README, and dotfiles."""
    return [
        p
        for p in changelog_dir.iterdir()
        if p.is_file() and not p.name.startswith(("_", ".")) and p.name != "README.rst"
    ]


def compute_version() -> str | None:
    """Return the next release version string, or *None* if there are no fragments."""
    repo_root = Path(__file__).resolve().parent.parent
    changelog_dir = repo_root / "changelog"

    if not _changelog_fragments(changelog_dir):
        return None

    from packaging.version import Version
    from setuptools_scm import get_version

    raw = get_version(root=str(repo_root))
    ver = Version(raw)
    return f"{ver.major}.{ver.minor}.{ver.micro}"


def main() -> int:
    version = compute_version()
    if version is None:
        print("No changelog fragments found — nothing to release.", file=sys.stderr)
        return 1
    print(version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
