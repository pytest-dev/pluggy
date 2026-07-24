# 01 — Module reorganization

**Status:** Foundation step (behavior-preserving move)
**Depends on:** nothing
**Next:** [02-configuration-objects.md](02-configuration-objects.md)

## Problem

On `main`, hook machinery is concentrated in:

| File | Contents today |
|------|----------------|
| [`src/pluggy/_hooks.py`](../src/pluggy/_hooks.py) | TypedDicts, markers, callers, HookImpl, HookSpec, helpers |
| [`src/pluggy/_callers.py`](../src/pluggy/_callers.py) | `_multicall`, old-style wrapper adapter |

Later steps (Protocols, CompletionHook, typed impls) need clear module
boundaries. try-claude already performed this split.

## Goals

- Split by role into focused modules (try-claude layout, clearer names OK).
- Preserve import paths via re-exports from `_hooks.py` / shims.
- Zero behavior change in this step.

## Non-goals

- New types, CompletionHook, Protocol callers (docs 02–05).
- Copying anything from `reiterate-claude`.

## Target design (chosen)

Cross-check summary:

| Branch | Layout | Notes |
|--------|--------|-------|
| `try-claude` | `_hook_config`, `_hook_markers`, `_hook_callers` (callers+impls), `_callers` | Good role split; `_hook_callers` too large; `_hook_*` + `_callers` naming clash |
| `reiterate-claude` | `_config`, `_decorators`, `_caller`, `_implementation`, `_execution` | Cleaner names; **do not copy its logic** |
| **This step** | reiterate **names** + current `main` **content** | Move-only |

```text
src/pluggy/
  _config.py           # HookspecOpts, HookimplOpts, normalize_hookimpl_opts
  _decorators.py       # markers, HookSpec, varnames
  _caller.py           # HookCaller, HookRelay, _SubsetHookCaller
  _implementation.py   # HookImpl + _Plugin / _HookImplFunction
  _execution.py        # _multicall + wrapper helpers
  _hooks.py            # re-exports (compat)
  _callers.py          # thin re-export of _execution (compat)
```

Name mapping from try-claude: see [DECISIONS.md](DECISIONS.md) D1. For this
step, move **current `main` code** only — do not yet port try-claude’s new
types/Protocols.

## Reference branch / files

```bash
# Layout inspiration only — content for step 01 is current main
git show try-claude:src/pluggy/_hook_config.py
git show try-claude:src/pluggy/_hook_markers.py
git show try-claude:src/pluggy/_hook_callers.py
git show try-claude:src/pluggy/_callers.py
git show try-claude:src/pluggy/_hooks.py
```

## Implementation steps

1. Create modules; cut-and-paste from `main`.
2. Fix relative imports; avoid cycles (`TYPE_CHECKING` where needed).
3. `_hooks.py` re-exports prior public/internal names.
4. Thin-shim or delete `_callers.py` after updating internal imports to
   `_execution`.
5. Verify:

```bash
uv run pytest
uv run pre-commit run -a
```

Commit message:

```text
chore(structure): split hook modules into _config, _decorators, _caller, _implementation, _execution
```

## Public API / back-compat

- `from pluggy import ...` unchanged.
- `from pluggy._hooks import ...` unchanged via re-exports.

## Tests

- No new semantic tests; suite must stay green.

## Done when

- [ ] Role modules exist; `_hooks.py` is re-export layer.
- [ ] Move-only diff (no intentional behavior change).
- [ ] pytest + pre-commit green.
