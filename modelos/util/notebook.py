from typing import Any
import inspect
import sys
import os
import ast
from IPython.core.magics.code import extract_symbols
from IPython.core.getipython import get_ipython
from nbconvert import PythonExporter
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


def find_import_statements():
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


class DependencyExtractor(ast.NodeVisitor):
    def __init__(self):
        self.dependencies = set()

    def visit_Name(self, node):
        self.dependencies.add(node.id)

    def visit_Attribute(self, node):
        self.dependencies.add(node.attr)


def extract_dependencies(code):
    tree = ast.parse(code)
    extractor = DependencyExtractor()
    extractor.visit(tree)
    return extractor.dependencies


def extract_class_from_notebook(notebook_path, class_name, output_file):
    if not os.path.exists(notebook_path):
        raise ValueError("notebook path does not exist")

    with open(notebook_path, "r") as f:
        ln = f.read()
        if len(ln) < 2:
            raise ValueError("Notebook exists but is empty, maybe you need to save?")

    # Convert the Jupyter notebook to a Python script
    exporter = PythonExporter()
    code, _ = exporter.from_filename(notebook_path)

    # Find the main class definition
    class_def = None
    for node in ast.parse(code).body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            class_def = node
            break

    if class_def is None:
        raise ValueError(f"Class {class_name} not found in the notebook {notebook_path}")

    # Get the class code and its dependencies
    class_code = code[class_def.col_offset : class_def.end_col_offset].strip()  # noqa
    dependencies = extract_dependencies(class_code)

    # Extract definitions that the class depends on
    definitions = []
    for node in ast.parse(code).body:
        if (
            isinstance(node, ast.Import)
            or isinstance(node, ast.ImportFrom)
            or isinstance(node, ast.FunctionDef)
            or isinstance(node, ast.Assign)
        ):
            for target in ast.walk(node):
                print("target: ", target)
                if isinstance(target, ast.Name) and target.id in dependencies:
                    definitions.append(code[node.col_offset : node.end_col_offset].strip())  # noqa
                    break

    # Create output file
    with open(output_file, "w") as f:
        # Write imports, functions, and variables to the output file
        for definition in definitions:
            f.write(definition)
            f.write("\n\n")

        # Write the class definition to the output file
        f.write(class_code)

    print(f"Successfully extracted class {class_name} into {output_file}")
