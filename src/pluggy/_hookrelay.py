"""
separate module for only hookrelay as mypyc doesnt support dynamic attributes/getattr
"""

from __future__ import annotations

from typing import final, TYPE_CHECKING

if TYPE_CHECKING:
    from pluggy import HookCaller


@final
class HookRelay:
    """Hook holder object for performing 1:N hook calls where N is the number
    of registered plugins."""

    __slots__ = ("__dict__",)

    def __init__(self) -> None:
        """:meta private:"""

    if TYPE_CHECKING:

        def __getattr__(self, name: str) -> HookCaller: ...
