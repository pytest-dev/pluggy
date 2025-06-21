# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pluggy is a minimalist production-ready plugin system that serves as the core framework for pytest, datasette and devpi.
It provides hook specification and implementation mechanisms through a plugin manager system.

## Development Commands

### Testing
- `uv run pytest` - Run all tests, prefer runnign all tests to quickly get feedback
- `uv run pytest testing/benchmark.py` runs the benchmark tests
- `tox` - Run tests across multiple Python versions (py39, py310, py311, py312, py313, pypy3)
- `tox -e py39` - Run tests on specific Python version
- `tox -e benchmark` - Run benchmarks
- `tox -e py39-pytestmain` - Test against pytest main branch

### Code Quality
- `uv run pre-commit run -a` - Run all pre-commit hooks - gives linting and typing errors + corrects files
- reread files that get fixed by pre-commit

### Documentation
- `tox -e docs` - Build documentation
- `python scripts/towncrier-draft-to-file.py` - Generate changelog draft to verify

### Release
## Core Architecture

### Main Components

- always read all python files in `src/pluggy/ to have full context`
- **PluginManager** (`src/pluggy/_manager.py`): Central registry that manages plugins and coordinates hook calls
- **HookCaller** (`src/pluggy/_hooks.py`): Executes hook implementations with proper argument binding
- **HookImpl/HookSpec** (`src/pluggy/_hooks.py`): Represent hook implementations and specifications
- **Result** (`src/pluggy/_result.py`): Handles hook call results and exception propagation
- **Multicall** (`src/pluggy/_callers.py`): Core execution engine for calling multiple hook implementations

### Key Concepts
- **Hook Specifications**: Define the interface (`@hookspec` decorator)
- **Hook Implementations**: Provide the actual functionality (`@hookimpl` decorator)
- **Plugin Registration**: Plugins are registered with the PluginManager
- **Hook Calling**: The manager coordinates calls to all registered implementations

### Package Structure
- `src/pluggy/` - Main package source
- `testing/` - Test suite using pytest
- `docs/` - Sphinx documentation and examples
- `changelog/` - Towncrier fragments for changelog generation

## Configuration Files
- `pyproject.toml` - Project metadata, build system, tool configuration (ruff, mypy, setuptools-scm)
- `tox.ini` - Multi-environment testing configuration
- `.pre-commit-config.yaml` - Code quality automation (ruff, mypy, flake8, etc.)

## Testing Notes
- Tests are located in `testing/` directory
- Uses pytest with coverage reporting
- Benchmark tests in `testing/benchmark.py`
- Minimum pytest version: 8.0
- Test configuration in `[pytest]` section of `tox.ini`
