from typing import Any
import inspect

from .notebook import get_notebook_class_code, is_notebook


def get_source(obj: Any) -> str:
    """Get source for an object in a robust way

    Args:
        obj (Any): Object to get source for

    Returns:
        str: Source code
    """
    if is_notebook():
        return get_notebook_class_code(obj)

    return inspect.getsource(obj)
