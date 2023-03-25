import ast
import os
from typing import get_args, Any, get_type_hints, Type, Dict, Optional
from types import NoneType
import logging
from importlib.metadata import version
import inspect

from modelos.object.encoding import is_first_order, is_list, is_dict, is_tuple, is_union, is_enum
from modelos.pkg.scheme.python import PythonPkg
from modelos.config import Config
from modelos.env.image.build import img_command
from modelos.object.repo.uri import remote_objrepo_from_uri
from .id import ObjectID


class ClientPkg(PythonPkg):
    """A package for an object client"""

    def load(self) -> Any:  # TODO: this should be generic?
        """Load the client class dynamically

        Returns:
            Any: A client class
        """
        raise NotImplementedError()


class ObjectPkg(PythonPkg):
    """A package for an object"""

    exec_path: Optional[str] = None

    def load(self) -> Any:  # TODO: this should be generic?
        """Load the object dynamically

        Returns:
            Any: A client class
        """
        raise NotImplementedError()

    def build(self, obj_repo: Optional[str] = None, labels: Optional[Dict[str, str]] = None) -> ObjectID:
        """Build the package into an executable

        Args:
            obj_repo (Optional[str], optional): Object repo to use. Defaults to None.
            labels (Optional[Dict[str, str]], optional): Labels to add. Defaults to None.

        Returns:
            ObjectID: An Object ID
        """
        if not obj_repo:
            obj_repo = Config().get_obj_repo()
            if not obj_repo:
                raise ValueError("could not find img repo to use")

        if self.exec_path is None:
            raise ValueError("Must set the exec_path property when building an image")

        project = self.project()
        repo = remote_objrepo_from_uri(obj_repo)
        cmd = img_command(self.exec_path, project)

        id = self.id()
        obj_id = repo.build(id.name, id.version, cmd, labels=labels, project=project)

        return obj_id

    def find_or_build(self, obj_repo: Optional[str] = None, labels: Optional[Dict[str, str]] = None) -> ObjectID:
        """Find or build the package into an executable

        Args:
            obj_repo (Optional[str], optional): Object repo to use. Defaults to None.
            labels (Optional[Dict[str, str]], optional): Labels to add. Defaults to None.

        Returns:
            ObjectID: An Object ID
        """
        if not obj_repo:
            obj_repo = Config().get_obj_repo()
            if not obj_repo:
                raise ValueError("could not find img repo to use")

        if self.exec_path is None:
            raise ValueError("Must set the exec_path property when building an image")

        project = self.project()
        repo = remote_objrepo_from_uri(obj_repo)
        cmd = img_command(self.exec_path, self.project())

        id = self.id()
        obj_id = repo.find_or_build(id.name, id.version, cmd, labels=labels, project=project)

        return obj_id


def is_same_project(mod_a: str, mod_b: str) -> bool:
    """Are the two modules in the same project

    Args:
        mod_a (str): Mod to check
        mod_b (str): Mod to check

    Returns:
        bool: Whether they are in the same project
    """

    a_parts = mod_a.split(".")
    b_parts = mod_b.split(".")

    return a_parts[0] == b_parts[0]


class AppendRoot(ast.NodeTransformer):
    """Append a new project root to imports conditionally"""

    root: str
    in_proj: Optional[str] = None

    def __init__(self, root: str, in_proj: Optional[str] = None) -> None:
        """Transform imports by adding a root to them

        Args:
            root (str): Root to add
            in_proj (Optional[str], optional): If present, will only add the root to modules defined in the
                    same project. Defaults to None.
        """
        self.root = root
        self.in_proj = in_proj

    def visit_Import(self, node: ast.Import):
        names = []
        for name in node.names:
            if self.in_proj:
                if is_same_project(self.in_proj, name.name):
                    name.name = f"{self.root}.{name.name}"
            else:
                name.name = f"{self.root}.{name.name}"
            names.append(name)
        node.names = names
        return node

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.level != 0:
            return node
        if self.in_proj:
            if node.module and is_same_project(self.in_proj, node.module):
                node.module = f"{self.root}.{node.module}"
        else:
            node.module = f"{self.root}.{node.module}"
        return node


def repackage(path: str, root: str, in_proj: Optional[str] = None) -> None:
    """Repackage a project adding a new root to imports

    Args:
        path (str): Path to the project
        root (str): Root to add
        in_proj (Optional[str], optional): If present will only append the root to modules defined
                                           in the same project. Defaults to None.
    """
    for rootpth, dirs, files in os.walk(path):
        for file in files:
            if ".py" in file:
                full_path = os.path.join(rootpth, file)
                with open(full_path, "r") as f:
                    tree = ast.parse(f.read())

                transformer = AppendRoot(root, in_proj)
                tree = transformer.visit(tree)
                code = ast.unparse(tree)

                with open(full_path, "w+") as f:
                    f.write(code)


def is_local_module(mod: str) -> bool:
    """Is this a local module

    Args:
        mod (str): Module to check

    Returns:
        bool: Whether this is a local module
    """

    return mod.startswith(".")


def get_module(t: Type) -> str:
    """Get the module for a type

    Args:
        t (Type): Type to get module for

    Returns:
        str: Module name
    """

    if hasattr(t, "__module__"):
        return t.__module__

    raise ValueError(f"type has no module: {t}")


def get_cls_modules(typ: Type) -> Dict[str, str]:
    """Get all related modules to a type

    Args:
        typ (Type): Type to check

    Returns:
        Dict[str, str]: Module to version map
    """

    print("t: ", typ)
    mod_typ = get_module(typ)

    ret: Dict[str, str] = {}

    no_add = ["__main__", "builtins"]

    def add_dep(name: str) -> None:
        nonlocal ret
        if name not in no_add and not is_same_project(mod_typ, name):
            name = name.split(".")[0]
            ret[name] = version(name)

    def _get_cls_modules(t: Type):
        nonlocal typ

        if t is None or t == NoneType:
            return

        if is_first_order(t):
            pass

        elif is_list(t):
            args = get_args(t)
            if len(args) == 0:
                raise SystemError(f"List must be typed: {t}")
            _get_cls_modules(args[0])

        elif is_dict(t):
            args = get_args(t)
            if len(args) != 2:
                raise SystemError(f"Dict must be typed: {t}")

            for arg in args:
                _get_cls_modules(arg)

        elif is_tuple(t):
            args = get_args(t)
            for arg in args:
                _get_cls_modules(arg)

        elif t == Any:
            pass

        elif is_union(t):
            args = get_args(t)
            if len(args) == 0:
                raise SystemError("args for iterable are None")

            for arg in args:
                _get_cls_modules(arg)

        elif is_enum(t):
            pass

        elif hasattr(t, "__annotations__"):
            mod = get_module(t)
            add_dep(mod)

            if is_same_project(mod, mod_typ) or is_local_module(mod) or mod == "__main__":
                try:
                    annots = get_type_hints(t)
                    for nm, typ in annots.items():
                        _get_cls_modules(typ)
                except Exception:
                    pass

        else:
            logging.warn(f"Do no know how to process param {t}")
            add_dep(get_module(t))

        mod = get_module(t)
        if is_same_project(mod, mod_typ) or is_local_module(mod) or mod == "__main__":
            fns = inspect.getmembers(t, predicate=inspect.isfunction)
            methods = inspect.getmembers(t, predicate=inspect.ismethod)

            fns.extend(methods)

            for name, fn in fns:
                sig = inspect.signature(fn, eval_str=True, follow_wrapped=True)
                print("sig: ", sig)
                for nm in sig.parameters:
                    parameter = sig.parameters[nm]
                    print("param: ", parameter)
                    _get_cls_modules(parameter.annotation)

                _get_cls_modules(sig.return_annotation)

    _get_cls_modules(typ)

    return ret


def build_requirements(deps: Dict[str, str]) -> str:
    """Build a requirements file

    Args:
        deps (Dict[str, str]): Deps to use

    Returns:
        str: A requirements.txt
    """
    ret = ""

    for k, v in deps.items():
        # TODO: need to handle version ranges
        ret += f"{k}=={v}\n"

    return ret


def build_setup(
    name: str,
    version: str,
    url: str,
    docs: str,
    code: str,
    tracker: str,
    maintainer: str,
    description: str,
    python_version: str,
) -> str:
    """Create a setup.py file for the given pkg data

    Args:
        name (str): Name of the project
        version (str): Version of the project
        deps (Dict[str, str]): Deps to add

    Returns:
        str: A serialized pyproject.toml
    """
    return f"""
from setuptools import find_packages
from setuptools import setup

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(
    name="{name}",
    version="{version}",
    url="{url}",
    install_requires=required,
    project_urls={{
        "Documentation": "{docs}",
        "Code": "{code}",
        "Issue tracker": "{tracker}",
    }},
    maintainer="{maintainer}",
    description="{description}",
    python_requires=">={python_version}",
    packages=[{name}],
)
    """
