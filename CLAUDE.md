# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pluggy is a minimalist production-ready plugin system that serves as the core framework for pytest, datasette and devpi.
It provides hook specification and implementation mechanisms through a plugin manager system.

## Development Commands

All commands use `uv run` for consistent environments.

### Testing
- `uv run pytest` - Run all tests (prefer running all tests for quick feedback)
- `uv run pytest testing/benchmark.py` - Run benchmark tests

### Code Quality
- `uv run pre-commit run -a` - Run all pre-commit hooks (linting, formatting, type checking)
- Always reread files modified by pre-commit

## Development Process

- Always read `src/pluggy/*.py` to get a full picture
- Consider backward compatibility
- Always run all tests: `uv run pytest`
- Always run pre-commit before committing: `uv run pre-commit run -a`
- Prefer running full pre-commit over individual tools (ruff/mypy)



## Core Architecture

### Main Components

- **PluginManager** (`src/pluggy/_manager.py`): Central registry that manages plugins and coordinates hook calls
- **HookCaller** (`src/pluggy/_hooks.py`): Executes hook implementations with proper argument binding
- **HookImpl/HookSpec** (`src/pluggy/_hooks.py`): Represent hook implementations and specifications
- **Result** (`src/pluggy/_result.py`): Handles hook call results and exception propagation
- **Multicall** (`src/pluggy/_callers.py`): Core execution engine for calling multiple hook implementations

### Package Structure
- `src/pluggy/` - Main package source
- `testing/` - Test suite using pytest
- `docs/` - Sphinx documentation and examples
- `changelog/` - Towncrier fragments for changelog generation

## Configuration Files
- `pyproject.toml` - Project metadata, build system, tool configuration (ruff, mypy, setuptools-scm)
- `tox.ini` - Multi-environment testing configuration
- `.pre-commit-config.yaml` - Code quality automation (ruff, mypy, flake8, etc.)
