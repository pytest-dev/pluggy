This directory contains tooling for testing some downstream projects against
your current pluggy checkout.

Each project is described by a TOML recipe in `recipes/` with three sections:

1. **`[git]`** — repository URL, local directory name (`into`), optional `shallow`
   (default: shallow clone).
2. **`[environment]`** — distinguished by structure (no `kind` key needed):
   - **uv-venv** (has `editables`): creates `uv venv`, installs via
     `uv pip install`.  `editables` are passed as `-e` args.  Optional
     `groups` and `packages` for extra dependencies.
   - **script** (has `run`): delegates bootstrap, install, and test to a
     bash script (path relative to `downstream/`).  No `[[test]]` steps.
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
