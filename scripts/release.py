"""Release script — local fallback for the automated CI pipeline.

Typical CI usage (automated):
    The ``prepare-release`` GitHub Actions workflow uses
    ``python -m setuptools_scm --strip-dev`` and handles branching,
    towncrier, and PR creation automatically.

Manual usage::

    tox -e release            # auto-detect version from fragments
    tox -e release -- 1.7.0   # explicit version override
"""

from __future__ import annotations

import argparse
from subprocess import check_call
from subprocess import check_output
import sys

from colorama import Fore
from colorama import init
from git import Remote
from git import Repo


def compute_version_auto() -> str:
    """Derive the next release version via ``setuptools_scm --strip-dev``."""
    version = (
        check_output(
            [sys.executable, "-m", "setuptools_scm", "--strip-dev"],
        )
        .decode()
        .strip()
    )
    if not version:
        raise RuntimeError("setuptools_scm returned an empty version.")
    return version


def create_branch(version: str) -> Repo:
    """Create a fresh branch from upstream/main."""
    repo = Repo.init(".")
    if repo.is_dirty(untracked_files=True):
        raise RuntimeError("Repository is dirty, please commit/stash your changes.")

    branch_name = f"release-{version}"
    print(f"{Fore.CYAN}Create {branch_name} branch from upstream main")
    upstream = get_upstream(repo)
    upstream.fetch()
    release_branch = repo.create_head(branch_name, upstream.refs.main, force=True)
    release_branch.checkout()
    return repo


def get_upstream(repo: Repo) -> Remote:
    """Find upstream repository for pluggy on the remotes."""
    for remote in repo.remotes:
        for url in remote.urls:
            if url.endswith(("pytest-dev/pluggy.git", "pytest-dev/pluggy")):
                return remote
    raise RuntimeError("could not find pytest-dev/pluggy remote")


def pre_release(version: str) -> None:
    """Create release branch and build changelog."""
    create_branch(version)
    changelog(version, write_out=True)

    check_call(["git", "commit", "-a", "-m", f"Preparing release {version}"])

    print()
    print(f"{Fore.GREEN}Please push your branch to your fork and open a PR.")


def changelog(version: str, *, write_out: bool = False) -> None:
    addopts: list[str] = [] if write_out else ["--draft"]
    print(f"{Fore.CYAN}Generating CHANGELOG")
    check_call(["towncrier", "build", "--yes", "--version", version, *addopts])


def main() -> int:
    init(autoreset=True)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "version",
        nargs="?",
        default=None,
        help="Release version (auto-detected from fragments if omitted)",
    )
    options = parser.parse_args()
    try:
        version = options.version or compute_version_auto()
        print(f"{Fore.CYAN}Release version: {version}")
        pre_release(version)
    except RuntimeError as e:
        print(f"{Fore.RED}ERROR: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
