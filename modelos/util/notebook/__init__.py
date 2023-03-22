from typing import Any, List, Type
import inspect
import sys
import ast

from IPython.core.magics.code import extract_symbols
from IPython.core.getipython import get_ipython
import IPython


def get_all_notebook_code() -> str:
    """Get all notebook code which has been executed as a single string

    Returns:
        str: All executed code
    """
    shell = get_ipython()
    fin = ""
    for r in shell.history_manager.get_range():
        fin += r[2]
        fin += "\n"

    return fin


def find_import_statements() -> List[str]:
    """Get all import statements for a notebook

    Returns:
        List[str]: List of import statements
    """
    import_statements = set()

    # Get the current Jupyter Notebook cells
    shell = IPython.get_ipython()
    cells = shell.user_ns["In"]

    for cell in cells:
        try:
            # Parse the cell content as an Abstract Syntax Tree (AST)
            parsed_cell = ast.parse(cell)

            for node in ast.walk(parsed_cell):
                # Check if the node is an import or import-from statement
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    import_statements.add(ast.unparse(node))

        except (SyntaxError, ValueError):
            # Skip cells that cannot be parsed as Python code
            pass

    return list(import_statements)


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


def is_notebook_cls(cls: Type) -> bool:
    """Check if the class was defined in a running notebook

    Args:
        cls (Type): Class to check

    Returns:
        bool: Whether the class is defined in a notebook
    """
    if not is_notebook():
        return False
    if cls.__module__ != "__main__":
        return False

    return True
