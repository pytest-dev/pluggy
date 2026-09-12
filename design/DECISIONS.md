# Design decisions (try-claude authority)

Experimental work on **`try-claude`** established the intended architecture.
**`reiterate-claude` was a failed experiment** that destroyed good abstractions
(unused subclasses, flag-driven multicall, CompletionHook removed, ephemeral
submitter monkeypatch, class-hierarchy callers instead of Protocols). Do **not**
copy reiterate logic. At most skim it for accidental rename ideas; never treat
it as design authority.

**Primary reference:** `try-claude` / `origin/try-claude-backup`.

## D1 — Module layout

**Decision:** Split roles into focused modules. Prefer try-claude’s split,
renamed for clarity if needed:

| try-claude | Target |
|------------|--------|
| `_hook_config.py` | `_config.py` |
| `_hook_markers.py` | `_decorators.py` |
| `_hook_callers.py` | `_caller.py` (callers + Protocol) + `_implementation.py` (HookImpl hierarchy) |
| `_callers.py` | `_execution.py` (multicall + CompletionHook orchestration) |
| `_project.py` / `_async.py` | same names |

`_hooks.py` remains a thin re-export/compat layer where useful.

**Rejected:** Anything from reiterate’s weakened `_execution` / `_caller` /
`_implementation` bodies.

## D2 — HookCaller: runtime_checkable Protocols (critical)

**Decision:** `HookCaller` is a `@runtime_checkable` `Protocol`. Concrete
callers (`NormalHookCaller`, `HistoricHookCaller`, `SubsetHookCaller`)
structurally implement it. Use Protocols elsewhere for exec/monitoring
boundaries where try-claude did (`_HookExec`, `CompletionHook`, …).

**Rejected:** reiterate’s concrete inheritance hierarchy that erased the
interface contract.

**Why:** Checkable protocols are how we type and isinstance-test callers
without freezing a brittle base class. This is a **critical** design point,
not optional polish.

## D3 — CompletionHook teardown (critical)

**Decision:** Wrappers expose teardown as `CompletionHook`:

```python
@runtime_checkable
class CompletionHook(Protocol):
    def __call__(
        self,
        result: object | list[object] | None,
        exception: BaseException | None,
    ) -> tuple[object | list[object] | None, BaseException | None]: ...
```

`WrapperImpl.setup_and_get_completion_hook(hook_name, caller_kwargs)` runs
setup (`next(gen)`) and returns the completion closure. Old-style wrappers
are adapted *inside* that method via `run_old_style_hookwrapper`.

`_multicall` phases:

1. Setup wrappers → collect `CompletionHook`s
2. Run `NormalImpl`s (arg bind via `_get_call_args`)
3. Run completion hooks LIFO; each may replace `(result, exception)`
4. Raise or return

**Rejected:** reiterate’s “CompletionHook no longer needed” adapter + flag
dispatch inside multicall. That is the failed simplification.

**Why:** CompletionHook is the critical enhancement that simplifies the
inner hook engine: multicall orchestrates phases; wrappers own
setup/teardown; no `.wrapper` / `.hookwrapper` branching in the hot loop.

## D4 — New types end-to-end; TypedDicts are gone

**Decision:** Live API uses configuration **classes** and impl **subclasses**:

- `HookspecConfiguration` / `HookimplConfiguration` (`__slots__` + `Final`)
- `HookImpl` / `NormalImpl` / `WrapperImpl`
- `HookimplConfiguration.create_hookimpl(...) -> NormalImpl | WrapperImpl`
  (fix try-claude footgun: normals must be `NormalImpl`, not bare `HookImpl`)
- Typed split lists on `NormalHookCaller`; dual-sequence `_multicall`

**TypedDicts (`HookspecOpts` / `HookimplOpts`) are removed from the public
and internal live path.** They are not “kept for compatibility.”

**Pytest support shim only:** a narrow compatibility helper (for pytest /
downstream that still hand-builds dict-shaped options during migration) may
accept mappings and convert them into configuration objects. That shim is
not the API; the API is the configuration classes. Do not re-export
TypedDicts as the preferred types in `__all__`.

**Rejected:** reiterate’s unused subclasses; keeping TypedDicts as the
long-term dual API.

## D5 — Async: persistent Submitter (try-claude)

**Decision:** `PluginManager` owns a `Submitter`, threaded through
`_hookexec` / callers into `_multicall`. `maybe_submit` on awaitable normal
results; inactive = pass-through (await-me-maybe).
`await pm.run_async(...)` → `Submitter.run`. Optional `pluggy[async] =
["greenlet"]`.

**Rejected:** reiterate’s ephemeral Submitter + `_inner_hookexec` monkeypatch.

## D6 — ProjectSpec

**Decision:** Additive hub. Markers and `PluginManager` accept
`str | ProjectSpec` (try-claude).

## D7 — Result and tracing

**Decision:** Keep `Result` / `TagTracer` public APIs. Update monitoring /
`_hookexec` signatures for split lists, submitter, and CompletionHook-era
multicall. Tracing callbacks may receive a combined impl list for back-compat
of the before/after hook shapes (as try-claude did).

## D8 — Bugs to fix when porting try-claude

1. `create_hookimpl` → return `NormalImpl` for non-wrappers.
2. `Submitter.run` → sentinel instead of `if result is None` failure.
3. Normal list typed as `list[NormalImpl]`.
4. Remove TypedDict definitions from the live API surface; isolate any dict
   acceptance in an explicit pytest/support shim module or helper.

## Reference

```bash
git show try-claude:src/pluggy/_hook_callers.py
git show try-claude:src/pluggy/_callers.py
git show try-claude:src/pluggy/_hook_config.py
git show try-claude:src/pluggy/_async.py
git show try-claude:testing/test_async.py
git show try-claude:testing/test_hookcaller.py
git show try-claude:testing/test_project_spec.py
```

Do not use `reiterate-claude` as a logic source.
