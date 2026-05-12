This directory contains tooling for testing some downstream projects against
your current pluggy checkout.

Each project is described by a TOML recipe in `recipes/` with three top-level
sections:

1. **`[git]`** — repository URL, local directory name (`into`), optional `shallow`
   (default: shallow clone).
2. **`[environment]`** — how the project is set up:
   - `kind = "uv-venv"` — `uv venv venv` in the clone root, then install via
     `uv pip install`.  **`[environment.install]`** holds **`editables`**: strings
     passed as `-e` arguments (e.g. `".[dev]"`, `"../.."`).  Optional
     **`[environment.install.uv]`** adds `groups` and `packages`.
   - `kind = "script"` — delegate everything (bootstrap, install, test) to a
     bash script via **`run`** (path relative to `downstream/`).  No `[[test]]`
     steps are used; the script handles the full workflow.
3. **`[[test]]`** (uv-venv only) — one or more `argv` arrays.  The driver sets
   **`VIRTUAL_ENV`** and prepends the venv's `bin` to **`PATH`**, so test
   commands can use bare names like `pytest`.  Optional **`env`** table sets
   extra environment variables; an empty string removes the variable (e.g.
   `env = { CI = "" }` to unset `CI`).
   Install only: `--only-install`.  Skip install: `--skip-install`.

Run the driver (PEP 723 in `run_downstream.py`):

```bash
uv run downstream/run_downstream.py --list
uv run downstream/run_downstream.py pytest
uv run downstream/run_downstream.py pytest --skip-install
```

Requirements: Python 3.11+ for the driver, `git`, and `uv`.
