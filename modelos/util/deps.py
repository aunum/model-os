from typing import Type, List, Union, Set, Tuple
import inspect
from pathlib import Path
import ast
import os
from importlib.machinery import ModuleSpec
from importlib.util import find_spec
from importlib.metadata import version

from modelos.project import Project


def find_imports(fp: str) -> List[Union[ast.Import, ast.ImportFrom]]:
    """Find imports for a filepath

    Args:
        fp (str): Filepath to find imports for

    Returns:
        List[Union[ast.Import, ast.ImportFrom]]: A list of AST import nodes
    """
    with open(fp, "r") as file:
        source_code = file.read()

    tree = ast.parse(source_code)
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
            imports.append(node)

    return imports


def is_stdlib(spec: ModuleSpec) -> bool:
    """Check if the given module spec is in the stdlib

    Args:
        spec (ModuleSpec): Spec to check

    Returns:
        bool: Whether it is in the stdlib
    """
    parts = spec.name.split(".")
    if len(parts) > 1:
        _spec = find_spec(parts[0])
        if _spec is None:
            return False

    if spec.origin is None:
        return False

    os_spec = find_spec("os")
    if os_spec is None:
        raise ValueError("os spec should never be None, please raise an issue")

    if os.path.dirname(str(os_spec.origin)) == os.path.dirname(str(spec.origin)):
        return True

    return False


def _should_search(current: ModuleSpec, found: ModuleSpec) -> bool:
    if found.origin is None:
        return False

    if current.origin is None:
        raise ValueError("current origin should not be None, please raise issue")

    # check if this is a native module
    if is_stdlib(found):
        return False

    # check if they are in the same dir
    if os.path.normpath(os.path.dirname(current.origin)) == os.path.normpath(os.path.dirname(found.origin)):
        return True

    # check if it is a subpath
    if Path(os.path.normpath(os.path.dirname(current.origin))) in Path(os.path.normpath(found.origin)).parents:
        return True

    # check if they are in the same project
    project = Project()
    if project:
        root = project.rootpath
        if Path(os.path.normpath(root)) in Path(os.path.normpath(found.origin)).parents:
            return True

    return False


def _should_add(current: ModuleSpec, found: ModuleSpec) -> bool:
    # check if this is a native module
    if is_stdlib(found):
        return False

    if found.origin is None:
        return False

    if current.origin is None:
        return False

    # check if they are in the same dir
    if os.path.normpath(os.path.dirname(current.origin)) == os.path.normpath(os.path.dirname(found.origin)):
        return False

    # check if it is a subpath
    if Path(os.path.normpath(os.path.dirname(current.origin))) in Path(os.path.normpath(found.origin)).parents:
        return False

    # check if they are in the same project
    project = Project()
    if project:
        root = project.rootpath
        if Path(os.path.normpath(root)) in Path(os.path.normpath(found.origin)).parents:
            return False

    return True


def _mods_to_search(spec: ModuleSpec) -> List[ModuleSpec]:
    ret: List[ModuleSpec] = [spec]
    parts = spec.name.split(".")

    if len(parts) > 1:
        for i, _ in enumerate(parts):
            mod = ".".join(parts[:-i])
            if mod != "":
                sub_spec = find_spec(mod)
                if sub_spec is None:
                    continue
                ret.append(sub_spec)

    return ret


# TODO: Another way to do this may be to launch a subprocess and check the globals there
# would need to use spawn instead of fork
def get_deps_for_type(t: Type) -> List[Tuple[str, str]]:
    """Get all external dependencies for the given type

    Args:
        t (Type): The type to check

    Returns:
        List[Tuple[str, str]]: A list of dep to version
    """
    mod = inspect.getmodule(t)
    if mod is None:
        raise ValueError("type given has no module")

    fp = inspect.getfile(t)

    fin: Set[Tuple[str, str]] = set()
    found: Set[str] = set()

    def add(current: ModuleSpec, found: ModuleSpec):
        nonlocal fin

        if _should_add(current, found):
            base_name = found.name.split(".")[0]

            ver = version(base_name)
            fin.add((base_name, ver))

    def _find_in_spec(spec: ModuleSpec):
        nonlocal fin
        imports = find_imports(fp)

        for imp in imports:
            if isinstance(imp, ast.ImportFrom):
                if imp.module is None:
                    raise ValueError("import modules should not be none, please raise issue")

                if imp.level > 0:
                    # local import
                    _spec = find_spec(imp.module, spec.name)
                    if _spec is None:
                        continue
                    if _spec.name in found:
                        continue
                    found.add(_spec.name)

                    add(spec, _spec)
                    if _should_search(spec, _spec):
                        for s in _mods_to_search(_spec):
                            _find_in_spec(s)

                else:
                    # global import
                    _spec = find_spec(imp.module)
                    if _spec is None:
                        continue
                    if _spec.name in found:
                        continue
                    found.add(_spec.name)

                    add(spec, _spec)
                    if _should_search(spec, _spec):
                        for s in _mods_to_search(_spec):
                            _find_in_spec(s)

            elif isinstance(imp, ast.Import):
                for name in imp.names:
                    _spec = find_spec(name.name)
                    if _spec is None:
                        continue
                    if _spec.name in found:
                        continue
                    found.add(_spec.name)

                    add(spec, _spec)
                    if _should_search(spec, _spec):
                        for s in _mods_to_search(_spec):
                            _find_in_spec(s)

    spec = find_spec(mod.__name__)
    if spec is None:
        raise ValueError("type given has no module spec")
    _find_in_spec(spec)

    return list(fin)
