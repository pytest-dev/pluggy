import sys
from typing import Optional, List, cast

if sys.version_info >= (3, 8):
    from importlib import metadata as importlib_metadata
else:
    import importlib_metadata


class DistFacade:
    """Emulate a pkg_resources Distribution"""

    def __init__(self, dist: importlib_metadata.Distribution):
        self._dist = dist

    @property
    def project_name(self) -> str:
        return cast(str, self._dist.metadata["name"])

    def __getattr__(
        self, attr: str, default: Optional[object] = None
    ) -> Optional[object]:
        return cast(Optional[object], getattr(self._dist, attr, default))

    def __dir__(self) -> List[str]:
        return sorted(dir(self._dist) + list(super().__dir__()))
