# 06 — ProjectSpec

**Status:** Additive project hub API
**Depends on:** [03-markers-attach-config.md](03-markers-attach-config.md)
**May parallelize with:** docs 04–05
**Next (series):** [07-async-submitter.md](07-async-submitter.md) still depends on 05

## Problem

Projects today juggle a bare `project_name` string, separately constructed
`HookspecMarker` / `HookimplMarker`, and `PluginManager(project_name)`.
try-claude’s `ProjectSpec` unifies that hub and lets markers/managers accept
`str | ProjectSpec`.

## Goals

- Add `ProjectSpec` with `project_name`, `.hookspec`, `.hookimpl`,
  `create_plugin_manager()`, config helpers.
- Markers and `PluginManager` accept `str | ProjectSpec`.
- Export `ProjectSpec` from `pluggy`.

## Non-goals

- Changing the meaning of project_name matching.
- Forcing all callers to migrate off strings.

## Target design

```python
# src/pluggy/_project.py  (port try-claude)


class ProjectSpec:
    def __init__(
        self,
        project_name: str,
        plugin_manager_cls: type[PluginManager] | None = None,
    ) -> None: ...

    @property
    def hookspec(self) -> HookspecMarker: ...

    @property
    def hookimpl(self) -> HookimplMarker: ...

    def create_plugin_manager(self, **kwargs: Any) -> PluginManager: ...

    def get_hookspec_config(self, **kwargs) -> HookspecConfiguration: ...
    def get_hookimpl_config(self, **kwargs) -> HookimplConfiguration: ...
```

Markers / manager:

```python
def __init__(self, project_name_or_spec: str | ProjectSpec): ...


# PluginManager likewise; project_name becomes a property from the spec
```

## Reference branch / files

```bash
git show try-claude:src/pluggy/_project.py
git show try-claude:src/pluggy/_hook_markers.py   # str | ProjectSpec
git show try-claude:src/pluggy/_manager.py
git show try-claude:testing/test_project_spec.py
git show try-claude:testing/benchmark.py          # ProjectSpec usage
```

## Implementation steps

1. Add `_project.py` from try-claude.
2. Teach markers + `PluginManager` to accept `str | ProjectSpec`.
3. Export from `__init__.py`.
4. Port `testing/test_project_spec.py`.
5. Update benchmark if it benefits from ProjectSpec helpers.

```bash
uv run pytest && uv run pre-commit run -a
```

Commit message:

```text
feat(project): add ProjectSpec hub for markers and PluginManager
```

## Public API / back-compat

- Additive: strings still work everywhere.
- New: `ProjectSpec` and dual acceptance.

## Tests

| File | Coverage |
|------|----------|
| `testing/test_project_spec.py` | Port from try-claude |

## Done when

- [ ] `ProjectSpec` exported and tested.
- [ ] String and ProjectSpec construction paths both work.
- [ ] Suite green.
