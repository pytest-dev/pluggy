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

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator
from pydantic import ValidationError
import tomllib


class GitConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    into: str
    shallow: bool = True


class EnvironmentUv(BaseModel):
    """uv-venv: create venv, install editables + optional groups/packages."""

    model_config = ConfigDict(extra="forbid")

    editables: list[str] = Field(min_length=1)
    groups: list[str] = Field(default_factory=list)
    packages: list[str] = Field(default_factory=list)

    @field_validator("editables")
    @classmethod
    def editables_non_empty_strings(cls, v: list[str]) -> list[str]:
        for i, s in enumerate(v):
            if not s.strip():
                msg = f"editables[{i}] must be a non-empty string"
                raise ValueError(msg)
        return v


class EnvironmentScript(BaseModel):
    """script: delegate everything to a bash script."""

    model_config = ConfigDict(extra="forbid")

    run: str


Environment = Annotated[
    EnvironmentUv | EnvironmentScript,
    Field(union_mode="left_to_right"),
]


class TestStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    argv: list[str] = Field(min_length=1)
    env: dict[str, str] = Field(default_factory=dict)


class RecipeFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    git: GitConfig
    environment: Environment
    test: list[TestStep] = Field(default_factory=list)

    @model_validator(mode="after")
    def script_has_no_test_steps(self) -> RecipeFile:
        if isinstance(self.environment, EnvironmentScript) and self.test:
            msg = "script environments handle testing; [[test]] must be empty"
            raise ValueError(msg)
        return self


DOWNSTREAM_DIR = Path(__file__).resolve().parent
RECIPES_DIR = DOWNSTREAM_DIR / "recipes"

VENV_DIRNAME = "venv"


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


def subprocess_env(
    *,
    extra: Mapping[str, str] | None,
    venv_home: Path | None,
) -> dict[str, str]:
    env = {**os.environ, **(extra or {})}
    # Empty-string values mean "remove from environment".
    for key, val in env.items():
        if val == "":
            del env[key]
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


def ensure_uv_venv(root: Path) -> None:
    cfg = root / VENV_DIRNAME / "pyvenv.cfg"
    if cfg.is_file():
        return
    run_cmd(["uv", "venv", VENV_DIRNAME], cwd=root)


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


def build_uv_install_argv(*, venv_home: Path, env: EnvironmentUv) -> list[str]:
    py = str(venv_python(venv_home))
    args = ["uv", "pip", "install", "--python", py]
    for g in env.groups:
        args.extend(["--group", g])
    for spec in env.editables:
        args.extend(["-e", spec])
    for pkg in env.packages:
        args.append(pkg)
    return args


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

    if isinstance(profile, EnvironmentScript):
        script = DOWNSTREAM_DIR / profile.run
        run_cmd(["bash", str(script)], cwd=DOWNSTREAM_DIR)
        return

    # uv-venv path
    ensure_uv_venv(dest)
    venv_home = dest / VENV_DIRNAME

    if not skip_install:
        argv_i = build_uv_install_argv(venv_home=venv_home, env=profile)
        run_cmd(argv_i, cwd=dest, venv_home=venv_home)

    if not only_install:
        for step in recipe.test:
            run_cmd(
                step.argv,
                cwd=dest,
                env=step.env or None,
                venv_home=venv_home,
            )


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
