from typing import Type
import inspect

from .notebook import get_notebook_class_code, is_notebook


def get_source(cls: Type) -> str:
    """Get source for an object class in a robust way

    Args:
        obj (Any): Object to get source for

    Returns:
        str: Source code
    """
    if is_notebook():
        return get_notebook_class_code(cls)

    return inspect.getsource(cls)
