from typing import Optional

from typing_extensions import TypedDict


class HookSpecMarkerData(TypedDict):
    firstresult: bool
    historic: bool
    warn_on_impl: Optional[Warning]


class HookImplMarkerSpec(TypedDict):
    hookwrapper: bool
    optionalhook: bool
    tryfirst: bool
    trylast: bool
    specname: Optional[str]
