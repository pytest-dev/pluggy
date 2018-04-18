'''
Call loop machinery
'''
from .utils import HookCallError, _raise_wrapfail, _Result
from .legacy import _legacymulticall, _LegacyMultiCall
from .cythonized import _multicall

__all__ = [
    '_multicall', '_legacymulticall', '_LegacyMultiCall',
    'HookCallError', '_Result',
]
