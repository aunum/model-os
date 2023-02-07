"""The Generic module provides a means of accessing Generic class types from within class functions at runtime"""
# Copied from https://github.com/python/typing/issues/629#issuecomment-829629259

import typing
import inspect


class Proxy:
    """Proxy class offers a wrapper to hold runtime generic data"""

    def __init__(self, generic):
        object.__setattr__(self, "_generic", generic)

    def __getattr__(self, name):
        if typing._is_dunder(name):
            attr = getattr(self._generic, name)
            return attr
        origin = self._generic.__origin__
        obj = getattr(origin, name)
        if inspect.ismethod(obj) and isinstance(obj.__self__, type):

            def proxy_func(*a, **kw):
                return obj.__func__(self, *a, **kw)

            return proxy_func
        else:
            return obj

    def __setattr__(self, name, value):
        return setattr(self._generic, name, value)

    def __call__(self, *args, **kwargs):
        return self._generic.__call__(*args, **kwargs)

    def __repr__(self):
        return f"<{self.__class__.__name__} of {self._generic!r}>"


class RuntimeGeneric:
    """Runtime Generic offers a means of accessing type annotations at runtime from class methods"""

    def __class_getitem__(cls, key):
        generic = super().__class_getitem__(key)
        if getattr(generic, "__origin__", None):
            return Proxy(generic)
        else:
            return generic
