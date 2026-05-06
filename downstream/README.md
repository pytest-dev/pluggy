This directory contains tooling for testing some downstream projects against
your current pluggy checkout.

Each project is described by a TOML recipe in `recipes/` with three top-level
sections plus tests:

1. **`[git]`** — repository URL, local directory name (`into`), optional `shallow`
   (default: shallow clone).
2. **`[environment]`** — how the Python environment is created **once** (skipped
   if `venv/pyvenv.cfg` already exists):
   - `kind = "uv-venv"` — `uv venv venv` in the clone root.
   - `kind = "stdlib-venv"` — `python -m venv venv` in the clone root.
   - `kind = "none"` — do not create a venv (e.g. conda’s `dev/start` workflow).
   **`[environment.install]`** holds **`editables`**: strings passed as consecutive
   **`-e`** arguments to `uv pip install` or `pip install` (same forms you would
   type on the command line, e.g. `".[dev]"`, `"../.."`). Optional
   **`[environment.install.uv]`** (`groups`, `packages`) or
   **`[environment.install.pip]`** (`packages`) match the environment kind. For
   `kind = "none"`, **`[environment.install.bootstrap]`** with `source` is
   required (shell script sourced before pip). Rerun tests without reinstall:
   `uv run downstream/run_downstream.py --skip-install RECIPE`.
3. **`[[test]]`** — one or more `argv` arrays. For `uv-venv` / `stdlib-venv`, the
   driver sets **`VIRTUAL_ENV`** and prepends the venv’s `bin` (or `Scripts` on
   Windows) to **`PATH`**, so test commands can use bare names like `pytest`.
   Install only: `--only-install`.

Run the driver (PEP 723 in `run_downstream.py`):

```bash
uv run downstream/run_downstream.py --list
uv run downstream/run_downstream.py pytest
uv run downstream/run_downstream.py pytest --skip-install
```

Requirements: Python 3.11+ for the driver, `git`, and `uv` where recipes use it.
Recipes using `uv-venv` / `stdlib-venv` get an activated-style environment for
install and test subprocesses; conda recipes use `bash` and their own `dev/start`.
