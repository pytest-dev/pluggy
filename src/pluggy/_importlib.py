from __future__ import annotations

import sys
from typing import Callable, Iterable, Any

if sys.version_info >= (3, 8):
    from importlib.metadata import distributions
else:
    from importlib_metadata import distributions


class DistFacade:
    """Emulate a pkg_resources Distribution"""

    # turn Any to Distribution as soon as the typing details for them fit
    def __init__(self, dist: Any) -> None:
        self._dist = dist

    @property
    def project_name(self) -> str:
        name: str = self.metadata["name"]
        return name

    def __getattr__(self, attr: str, default: Any | None = None) -> Any:
        return getattr(self._dist, attr, default)

    def __dir__(self) -> list[str]:
        return sorted(dir(self._dist) + ["_dist", "project_name"])


def iter_entrypoint_loaders(
    group: str, name: str | None
) -> Iterable[tuple[DistFacade, str, Callable[[], object]]]:
    for dist in list(distributions()):
        legacy = DistFacade(dist)
        for ep in dist.entry_points:
            if ep.group == group and name is None or name == ep.name:
                yield legacy, ep.name, ep.load
