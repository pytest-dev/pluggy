# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic>=2.7",
# ]
# ///
from __future__ import annotations

import argparse
from collections.abc import Mapping
from collections.abc import Sequence
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator
from pydantic import ValidationError
import tomllib


class GitConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    into: str
    shallow: bool = True


class UvInstallOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    groups: list[str] = Field(default_factory=list)
    packages: list[str] = Field(default_factory=list)


class PipInstallOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packages: list[str] = Field(default_factory=list)


class BootstrapConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str


class _InstallEditables(BaseModel):
    model_config = ConfigDict(extra="forbid")

    editables: list[str] = Field(min_length=1)

    @field_validator("editables")
    @classmethod
    def editables_non_empty_strings(cls, v: list[str]) -> list[str]:
        for i, s in enumerate(v):
            if not s.strip():
                msg = f"editables[{i}] must be a non-empty string"
                raise ValueError(msg)
        return v


class UvInstall(_InstallEditables):
    uv: UvInstallOptions | None = None


class StdlibInstall(_InstallEditables):
    pip: PipInstallOptions | None = None


class NoneInstall(_InstallEditables):
    bootstrap: BootstrapConfig


class EnvironmentUv(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["uv-venv"]
    install: UvInstall


class EnvironmentStdlib(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["stdlib-venv"]
    install: StdlibInstall


class EnvironmentNone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["none"]
    install: NoneInstall


Environment = Annotated[
    EnvironmentUv | EnvironmentStdlib | EnvironmentNone,
    Field(discriminator="kind"),
]


class TestStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    argv: list[str] = Field(min_length=1)


class RecipeFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    git: GitConfig
    environment: Environment
    test: list[TestStep] = Field(min_length=1)


DOWNSTREAM_DIR = Path(__file__).resolve().parent
RECIPES_DIR = DOWNSTREAM_DIR / "recipes"

# Local venv layout is fixed (simplifies recipes).
VENV_DIRNAME = "venv"
PYTHONBIN_FOR_STDLIB_VENV_CREATE = "python"


def venv_bin_dir(venv_home: Path) -> Path:
    root = venv_home.resolve()
    posix = root / "bin"
    if posix.is_dir():
        return posix
    return root / "Scripts"


def venv_python(venv_home: Path) -> Path:
    d = venv_bin_dir(venv_home)
    for name in ("python", "python3", "python.exe"):
        candidate = d / name
        if candidate.is_file():
            return candidate
    return d / "python"


def venv_pip(venv_home: Path) -> Path:
    d = venv_bin_dir(venv_home)
    for name in ("pip", "pip.exe"):
        candidate = d / name
        if candidate.is_file():
            return candidate
    return d / "pip"


def subprocess_env(
    *,
    extra: Mapping[str, str] | None,
    venv_home: Path | None,
) -> dict[str, str]:
    env = {**os.environ, **dict(extra or {})}
    if venv_home is None:
        return env
    root = venv_home.resolve()
    bindir = venv_bin_dir(root)
    env["VIRTUAL_ENV"] = str(root)
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    return env


def echo_cmd(argv: Sequence[str], *, cwd: Path) -> None:
    display = shlex.join(argv)
    print(f"+ cd {cwd.as_posix()} && {display}", flush=True)


def run_cmd(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    venv_home: Path | None = None,
) -> None:
    echo_cmd(argv, cwd=cwd)
    merged_env = subprocess_env(extra=env, venv_home=venv_home)
    result = subprocess.run(
        list(argv),
        cwd=cwd,
        env=merged_env,
        check=False,
    )
    if result.returncode != 0:
        sys.exit(result.returncode)


def git_clone_or_pull(*, dest: Path, url: str, shallow: bool) -> None:
    if dest.is_dir():
        run_cmd(["git", "-C", str(dest), "pull", "--ff-only"], cwd=dest.parent)
        return
    args = ["git", "clone"]
    if shallow:
        args.extend(["--depth", "1"])
    args.extend([url, str(dest)])
    run_cmd(args, cwd=dest.parent)


def venv_pyvenv_cfg(root: Path) -> Path:
    return root / VENV_DIRNAME / "pyvenv.cfg"


def ensure_environment(*, root: Path, environment: Environment) -> None:
    if isinstance(environment, EnvironmentNone):
        return
    if venv_pyvenv_cfg(root).is_file():
        return
    if isinstance(environment, EnvironmentUv):
        run_cmd(["uv", "venv", VENV_DIRNAME], cwd=root)
    else:
        run_cmd(
            [PYTHONBIN_FOR_STDLIB_VENV_CREATE, "-m", "venv", VENV_DIRNAME],
            cwd=root,
        )


def format_validation_error(path_name: str, err: ValidationError) -> str:
    lines = [f"{path_name}: recipe validation failed"]
    for e in err.errors():
        loc = ".".join(str(x) for x in e["loc"])
        msg = e["msg"]
        lines.append(f"  {loc}: {msg}")
    return "\n".join(lines)


def load_recipe(name: str) -> RecipeFile:
    path = RECIPES_DIR / f"{name}.toml"
    if not path.is_file():
        available = ", ".join(sorted(p.stem for p in RECIPES_DIR.glob("*.toml")))
        print(f"Unknown downstream {name!r}. Available: {available}", file=sys.stderr)
        sys.exit(2)
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    try:
        return RecipeFile.model_validate(data)
    except ValidationError as e:
        print(format_validation_error(path.name, e), file=sys.stderr)
        sys.exit(2)


def build_uv_install_argv(*, venv_home: Path, install: UvInstall) -> list[str]:
    py = str(venv_python(venv_home))
    args: list[str] = ["uv", "pip", "install", "--python", py]
    uv = install.uv
    if uv is not None:
        for g in uv.groups:
            args.extend(["--group", g])
    for spec in install.editables:
        args.extend(["-e", spec])
    if uv is not None:
        for pkg in uv.packages:
            args.append(pkg)
    return args


def build_stdlib_install_argv(*, venv_home: Path, install: StdlibInstall) -> list[str]:
    pip_exe = str(venv_pip(venv_home))
    args: list[str] = [pip_exe, "install"]
    for spec in install.editables:
        args.extend(["-e", spec])
    pip_extra = install.pip
    if pip_extra is not None:
        for pkg in pip_extra.packages:
            args.append(pkg)
    return args


def build_bootstrap_install_argv(*, install: NoneInstall) -> list[str]:
    boot = install.bootstrap
    inner_pip: list[str] = ["pip", "install"]
    for spec in install.editables:
        inner_pip.extend(["-e", spec])
    script = (
        f"set +eu; source {shlex.quote(boot.source)}; set -eu; {shlex.join(inner_pip)}"
    )
    return ["bash", "-c", script]


def run_recipe(
    name: str,
    *,
    skip_install: bool = False,
    only_install: bool = False,
) -> None:
    recipe = load_recipe(name)
    dest = DOWNSTREAM_DIR / recipe.git.into
    git_clone_or_pull(dest=dest, url=recipe.git.url, shallow=recipe.git.shallow)
    profile = recipe.environment
    ensure_environment(root=dest, environment=profile)
    if isinstance(profile, EnvironmentNone):
        venv_home = None
    else:
        venv_home = dest / VENV_DIRNAME
    if not skip_install:
        if isinstance(profile, EnvironmentUv):
            argv_i = build_uv_install_argv(
                venv_home=venv_home,
                install=profile.install,
            )
        elif isinstance(profile, EnvironmentStdlib):
            argv_i = build_stdlib_install_argv(
                venv_home=venv_home,
                install=profile.install,
            )
        else:
            argv_i = build_bootstrap_install_argv(install=profile.install)
        run_cmd(argv_i, cwd=dest, venv_home=venv_home)
    if not only_install:
        for step in recipe.test:
            run_cmd(list(step.argv), cwd=dest, venv_home=venv_home)


def list_recipes() -> None:
    names = sorted(p.stem for p in RECIPES_DIR.glob("*.toml"))
    for n in names:
        print(n)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Clone or update a downstream project and run its check recipe.",
    )
    parser.add_argument(
        "downstream",
        nargs="?",
        help="Recipe name (see *.toml in downstream/recipes/)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print available recipe names and exit.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Run environment + tests only (reuse existing installs).",
    )
    parser.add_argument(
        "--only-install",
        action="store_true",
        help="Run environment + install phases only (skip tests).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if args.list:
        list_recipes()
        return
    if not args.downstream:
        parser.error("downstream recipe name is required (or use --list)")
    if args.only_install and args.skip_install:
        parser.error("--only-install and --skip-install are mutually exclusive")
    run_recipe(
        args.downstream,
        skip_install=args.skip_install,
        only_install=args.only_install,
    )


if __name__ == "__main__":
    main()
