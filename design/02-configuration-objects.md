# 02 — Configuration objects (TypedDicts removed)

**Status:** Replace live options encoding
**Depends on:** [01-module-reorganization.md](01-module-reorganization.md)
**Next:** [03-markers-attach-config.md](03-markers-attach-config.md)

## Problem

On `main`, options are `HookspecOpts` / `HookimplOpts` TypedDicts — unvalidated
dicts copied around as the live representation. try-claude introduced proper
configuration classes; those are the API.

## Goals

- Add `HookspecConfiguration` and `HookimplConfiguration` (`__slots__`,
  `Final`, validation).
- **Remove TypedDicts from the live and public API surface.**
- Provide a **narrow pytest support shim** that accepts mapping/dict-shaped
  options and converts them to configuration objects (pytest migration only).
- Export configuration classes from `pluggy`.

## Non-goals

- Keeping TypedDicts “for compatibility” as a dual API ([DECISIONS.md](DECISIONS.md) D4).
- Marker attachment (doc 03) — can land in the same PR if cleaner, but
  conceptually next.
- `create_hookimpl` body (needs NormalImpl/WrapperImpl — doc 04); may stub
  or add method signature with a TODO.

## Target design

```python
# src/pluggy/_config.py

class HookspecConfiguration:
    __slots__ = ("firstresult", "historic", "warn_on_impl", "warn_on_impl_args")
    firstresult: Final[bool]
    historic: Final[bool]
    warn_on_impl: Final[Warning | None]
    warn_on_impl_args: Final[Mapping[str, Warning] | None]

    def __init__(self, firstresult=False, historic=False, ...):
        if historic and firstresult:
            raise ValueError("cannot have a historic firstresult hook")
        ...

class HookimplConfiguration:
    __slots__ = ("wrapper", "hookwrapper", "optionalhook",
                 "tryfirst", "trylast", "specname")
    ...
    # create_hookimpl added in doc 04
```

Pytest support shim (name flexible — e.g. `_pytest_compat.py` or helpers in
`_config.py` marked clearly):

```python
def hookspec_config_from_mapping(opts: Mapping[str, Any]) -> HookspecConfiguration:
    """Pytest/support only: accept legacy dict-shaped options."""
    return HookspecConfiguration(
        firstresult=opts.get("firstresult", False),
        historic=opts.get("historic", False),
        warn_on_impl=opts.get("warn_on_impl"),
        warn_on_impl_args=opts.get("warn_on_impl_args"),
    )

def hookimpl_config_from_mapping(opts: Mapping[str, Any]) -> HookimplConfiguration:
    ...
```

Do **not** keep `TypedDict` classes in `__all__`. Do not document dicts as
the options API. Markers take kwargs that construct configuration objects
directly (doc 03).

## Reference branch / files

```bash
git show try-claude:src/pluggy/_hook_config.py
```

Port classes from try-claude; then **delete** the TypedDict definitions from
the live module (try still kept them — we go further per D4). Isolate mapping
helpers as the only dict-facing surface.

## Implementation steps

### Step 2.1 — Add configuration classes

Port from try-claude `_hook_config.py` into `_config.py`.

### Step 2.2 — Remove TypedDicts from live path

1. Delete `HookspecOpts` / `HookimplOpts` TypedDict definitions (or move to a
   private pytest-shim module if pytest tests in-tree still need the names
   during transition — prefer deletion + mapping helpers).
2. Update all internal imports/usages to configuration classes.
3. Update `__init__.py` exports: add configuration classes; drop TypedDict
   exports.

### Step 2.3 — Pytest support shim

1. Add `hookspec_config_from_mapping` / `hookimpl_config_from_mapping`.
2. Document in docstring: for pytest/support migration only, not the public
   options API.
3. If pytest (downstream) needs a temporary import path, keep it private
   (`pluggy._config` or `pluggy._pytest_compat`), not in `__all__`.

### Step 2.4 — Tests

- Validation (`historic` + `firstresult`).
- Mapping shim round-trip.
- No remaining tests that treat TypedDicts as the primary API.

```bash
uv run pytest
uv run pre-commit run -a
```

Commit message:

```text
feat(config): replace TypedDict options with Hook*Configuration classes
```

## Public API / back-compat

| Before | After |
|--------|-------|
| `HookspecOpts` / `HookimplOpts` TypedDicts | **Removed** from public API |
| dict attrs on marked functions | configuration objects (doc 03) |
| — | `HookspecConfiguration` / `HookimplConfiguration` exported |
| — | private mapping shim for pytest support |

Marker **kwargs** (`firstresult=`, `wrapper=`, …) stay — they construct
objects, they are not TypedDict literals.

## Tests to add/update

| File | Coverage |
|------|----------|
| `testing/test_configuration.py` | Class validation; mapping shim |
| Anything importing TypedDicts | Migrate or delete |

## Done when

- [ ] Configuration classes are the only live options encoding.
- [ ] TypedDicts gone from public `__all__` / docs path.
- [ ] Pytest mapping shim exists and is clearly non-API.
- [ ] pytest + pre-commit green.
