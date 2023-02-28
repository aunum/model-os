from typing import Any
import inspect
import sys
from IPython.core.magics.code import extract_symbols


def get_notebook_class_code(obj: Any) -> str:
    """Get the source code for an object defined in a notebook

    Args:
        obj (Any): Object to get code for

    Returns:
        str: Source code
    """

    def new_getfile(object, _old_getfile=inspect.getfile):
        if not inspect.isclass(object):
            return _old_getfile(object)

        # Lookup by parent module (as in current inspect)
        if hasattr(object, "__module__"):
            object_ = sys.modules.get(object.__module__)
            if hasattr(object_, "__file__"):
                return object_.__file__

        # If parent module is __main__, lookup by methods (NEW)
        for _, member in inspect.getmembers(object):
            if inspect.isfunction(member) and object.__qualname__ + "." + member.__name__ == member.__qualname__:
                return inspect.getfile(member)
        else:
            raise TypeError("Source for {!r} not found".format(object))

    inspect.getfile = new_getfile

    cell_code = "".join(inspect.linecache.getlines(new_getfile(obj)))  # type: ignore
    class_code = extract_symbols(cell_code, obj.__name__)[0][0]

    return class_code


def is_notebook() -> bool:
    """Check if the current process is a notebook

    Returns:
        bool: _description_
    """
    try:
        shell = get_ipython().__class__.__name__  # type: ignore
        if shell == "ZMQInteractiveShell":
            return True  # Jupyter notebook or qtconsole
        elif shell == "TerminalInteractiveShell":
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False  # Probably standard Python interpreter
